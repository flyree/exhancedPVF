import os
import sys
import re
import random
from networkx import graphviz_layout

import InstructionAbstraction
import networkx as nx
import matplotlib.pyplot as plt
import setting as config
import PVF as pvf
from bisect import bisect_left

sys.setrecursionlimit(10000)
counter = 0
phiNodeCheck = {}

def isfloat(x):
    try:
        a = float(x)
    except ValueError:
        return False
    else:
        return True


def isint(x):
    try:
        a = float(x)
        b = int(a)
    except ValueError:
        return False
    else:
        return a == b



def binary_search(a, x, lo=0, hi=None):   # can't use a to specify default for hi
    hi = hi if hi is not None else len(a) # hi defaults to len(a)
    pos = bisect_left(a,x,lo,hi)          # find insertion position
    return (a[pos] if pos != hi else -1)

class DDG:
    @classmethod
    def __init__(self, trace):
        assert(len(trace) == 3)
        self.dynamic_trace = trace[0]
        self.remap = trace[1]
        self.memory = trace[2]

    # ##
    # A node can be 1. source 2. dest 3. opcode
    # ##
    @classmethod
    def ddg_construct(self, trace, memcpyRec, bitwiseRec):
        global counter
        global phiNodeCheck
        global blacklist
        G = nx.DiGraph()
        multiInstance = {}
        rename_mapping = {}
        fm = InstructionAbstraction.FunctionMapping(config.IRpath)
        funcMap = fm.extractFuncDef()
        # format of funcmap: {funcname:[type/void, arg1, arg2 ...], funcname:[...]}
        flag_phi = 0
        totalbits = 0
        for idx, ddg_inst in enumerate(trace):
            # the following two lists hold the newly added nodes for the current instruction
            # the nodes can be either a operand or a memory address
            source_node = []
            dest_node = []
            instbits = 0
            #print idx
            #print ddg_inst.opcode
            #if idx == 2654:
            # print ddg_inst.input[0]
            # print ddg_inst.output[0]
            for source in ddg_inst.input:
                op = source.operand
                if op in rename_mapping.keys():
                    op = rename_mapping[op]
                if op not in multiInstance.keys():
                    multiInstance[op] = op
                else:
                    op = multiInstance[op]
                itype = 0
                ty1 = 0
                ty2 = 0
                if "+" in str(source.type):
                        ty1 = source.type.split("+")[0]
                        ty2 = source.type.split("+")[1]
                else:
                    ty1 = source.type
                if int(ty1) == 0:
                    itype = config.OSbits
                else:
                    itype = ty1
                if ddg_inst.opcode not in config.memoryInst:
                    if ddg_inst.funcname == "":
                        res = itype
                        instbits += int(res)
                        #print ddg_inst.opcode
                        #print itype
                        #print "#########"
                    else:
                        if ddg_inst.funcname not in config.intrinsics:
                            res = itype
                            instbits += int(res)

                if ddg_inst.address != -1:
                    if ddg_inst.opcode == "load":
                        address = ddg_inst.address
                        if address not in multiInstance.keys():
                            multiInstance[address] = address
                        else:
                            address = multiInstance[address]
                        if ddg_inst.address not in G.nodes():
                            index = self.remap[idx]
                            limit = binary_search(sorted(self.memory.keys()), index)
                            G.add_node(address, len=itype, size=1, operand0=op, mem=limit, index=ddg_inst.input.index(source))
                            G.add_node(op, len=itype,size=1, operand0=op,index=ddg_inst.input.index(source))
                            G.add_edge(address, op, opcode='virtual')
                            G.add_edge(op, address, opcode='virtual')
                            source_node.append(address)
                        else:
                            size = int(G.node[address]['size']) + 1
                            G.node[address]['size'] = size
                            G.node[address]['operand' + str(size - 1)] = op
                            source_node.append(address)
                            # create fake edges between the address and the register
                            G.add_node(op, len=itype,size=1, operand0=op,index=ddg_inst.input.index(source))
                            G.add_edge(address, op, opcode='virtual')
                            G.add_edge(op, address, opcode='virtual')
                            # addr_op_map[ddg_inst.address] = op
                    elif ddg_inst.opcode == "call":
                        if ddg_inst.funcname in funcMap.keys():
                            op_rep = funcMap[ddg_inst.funcname][ddg_inst.index(op) + 1]
                            rename_mapping[op_rep] = op
                    else:
                        #if op not in G.nodes():
                        #flag = 0
                        #for node in G.nodes():
                        #    for i in range(int(G.node[node]['size'])):
                        #        if G.node[node]['operand' + str(i)] == op:
                        #            source_node.append(node)
                        #            flag = 1
                        #            break
                        #if flag == 0:
                        if op not in G.nodes():
                            if isint(op) or isfloat(op):
                                counter += 1
                                op_new = "constant" + str(counter)
                                G.add_node(op_new, len=itype, size=1, operand0=op_new,index=ddg_inst.input.index(source), value=op)
                                source_node.append(op_new)
                            else:
                                G.add_node(op, len=itype, size=1, operand0=op,index=ddg_inst.input.index(source))
                                source_node.append(op)
                        else:
                            G.node[op]['index'] = ddg_inst.input.index(source)
                            source_node.append(op)
                else:
                    if ddg_inst.opcode == "call":
                        if ddg_inst.funcname in funcMap.keys():
                            op_rep = funcMap[ddg_inst.funcname][ddg_inst.index(op) + 1]
                            rename_mapping[op_rep] = op
                        if "memcpy" in ddg_inst.funcname:
                            # if op not in G.nodes():
                            #    flag = 0
                            #    for node in G.nodes():
                            #        for i in range(int(G.node[node]['size'])):
                            #            if G.node[node]['operand'+str(i)] == op:
                            #                source_node.append(node)
                            #                flag = 1
                            #                break
                            #    if flag == 0:
                            #        G.add_node(op, len=itype, size=1, operand0=op)
                            #        source_node.append(op)
                            #else:
                            #    source_node.append(op)
                            source_address = memcpyRec[self.remap[idx]][1]
                            length = memcpyRec[self.remap[idx]][2]
                            for i in range(int(length)):
                                if str(int(source_address) + i) in G.nodes():
                                    size = int(G.node[str(int(source_address) + i)]['size']) + 1
                                    G.node[str(int(source_address) + i )]['size'] = size
                                    G.node[str(int(source_address) + i )]['operand' + str(size - 1)] = op
                                    source_node.append(str(int(source_address) + i))
                                else:
                                    G.add_node(str(int(source_address) + i ), len=itype, size=1, operand0="")
                                    source_node.append(str(int(source_address) + i))
                    else:
                        #if op not in G.nodes():
                            if ddg_inst.opcode == "phi":
                                for i in xrange(idx, 0, -1):
                                    if len(trace[i].output) > 0:
                                        if trace[i].output[0].operand in op:
                                            phiNodeCheck[i] = op
                                            flag_phi = 1
                                            break
                            else:
                                if op not in G.nodes():
                                    if isint(op) or isfloat(op):
                                        counter += 1
                                        op_new = "constant" + str(counter)
                                        G.add_node(op_new, len=itype, size=1, operand0=op_new, value = op,index=ddg_inst.input.index(source))
                                        source_node.append(op_new)
                                    else:
                                        if ddg_inst.opcode == "and" or ddg_inst.opcode == "or" \
                                                or ddg_inst.opcode == "shl" or \
                                                        ddg_inst.opcode == "lshr" or ddg_inst.opcode == "ashr":
                                            G.add_node(op, len=itype, size=1,
                                                       operand0=op, bits=bitwiseRec[self.remap[idx]][ddg_inst.input.index(source)])
                                            source_node.append(op)
                                        else:
                                            G.add_node(op, len=itype, size=1, operand0=op,index=ddg_inst.input.index(source))
                                            source_node.append(op)
                        #else:
                            #if ddg_inst.opcode == "phi":
                            #    for i in xrange(idx, 0, -1):
                            #        if len(trace[i].output) > 0:
                            #            if trace[i].output[0].operand == op:
                            #                phiNodeCheck[i] = op
                            #                flag_phi = 1
                                else:
                                    G.node[op]['index'] = ddg_inst.input.index(source)
                                    source_node.append(op)
            if ddg_inst.opcode == "getelementptr":
                if "+" in str(ddg_inst.input[0].type):
                    new_split = ddg_inst.input[0].type.split("+")
                    if len(new_split) > 2:
                        G.node[multiInstance[ddg_inst.input[0].operand]]['realTy'] = new_split[1]
                        if isint(new_split[2]) or isfloat(new_split[2]) :
                            G.node[multiInstance[ddg_inst.input[0].operand]]['elementTy'] = new_split[2]
                        else:
                            G.node[multiInstance[ddg_inst.input[0].operand]]['structName'] = new_split[2]
                    else:
                        G.node[multiInstance[ddg_inst.input[0].operand]]['realTy'] = new_split[1]

            if flag_phi == 1:
                index = max(phiNodeCheck.keys())
                if phiNodeCheck[index] not in G.nodes():
                    for source in ddg_inst.input:
                        if source.operand == phiNodeCheck[index]:
                            pos = ddg_inst.input.index(source)
                            G.add_node(phiNodeCheck[index],len=itype, size=1,index=pos, value = ddg_inst.output[0].value)
                else:
                    G.node[phiNodeCheck[index]]['value'] = ddg_inst.output[0].value
                source_node.append(phiNodeCheck[index])
                phiNodeCheck = {}
                flag_phi = 0

            for dest in ddg_inst.output:
                op = dest.operand
                if op in rename_mapping.keys():
                    op = rename_mapping[op]
                if op not in multiInstance.keys():
                    multiInstance[op] = op
                else:
                    op = multiInstance[op]
                itype = 0
                if dest.type == 0:
                    itype = config.OSbits
                else:
                    itype = dest.type
                #if ddg_inst.opcode not in config.memoryInst:
                #    res = itype
                #    instbits += int(res)
                if ddg_inst.address != -1:
                    if ddg_inst.opcode == "store" or ddg_inst.opcode == "alloca":
                        address = ddg_inst.address
                        if address not in multiInstance.keys():
                            multiInstance[address] = address
                        else:
                            address = multiInstance[address]
                        if address not in G.nodes():
                            index = self.remap[idx]
                            limit = binary_search(sorted(self.memory.keys()), index)
                            G.add_node(address, len=itype, size=1, operand0=op, mem=limit)
                            dest_node.append(address)
                            G.add_node(op, len=itype,size=1, operand0=op)
                            G.add_edge(address, op, opcode='virtual')
                            G.add_edge(op, address, opcode='virtual')
                        else:
                            counter += 1
                            address = address.split("+")[0]
                            address1 = address+"+"+str(counter)
                            multiInstance[address] = address1
                            index = self.remap[idx]
                            limit = binary_search(sorted(self.memory.keys()),index)
                            G.add_node(address1, len=itype, size=1, operand0=op, mem=limit)
                            dest_node.append(address1)
                            G.add_node(op, len=itype, size=1, operand0=op)
                            G.add_edge(address1, op, opcode='virtual')
                            G.add_edge(op, address1, opcode='virtual')
                            # addr_op_map[ddg_inst.address] = op
                    elif ddg_inst.opcode == "call":
                        if ddg_inst.funcname in funcMap.keys():
                            op_rep = funcMap[ddg_inst.funcname][ddg_inst.index(op) + 1]
                            rename_mapping[op_rep] = op
                    else:
                        if op not in G.nodes():
                            #flag = 0
                            #for node in G.nodes():
                            #    for i in range(int(G.node[node]['size'])):
                            #        if G.node[node]['operand' + str(i)] == op:
                            #            dest_node.append(node)
                            #            flag = 1
                            #            break
                            #if flag == 0:
                            if ddg_inst.opcode == "load":
                                sop =ddg_inst.input[0].operand
                                if sop in multiInstance.keys():
                                    sop = multiInstance[sop]
                                G.add_node(op, len=itype, size=1, operand0=op, pre=sop, value = dest.value)
                            else:
                                G.add_node(op, len=itype, size=1, operand0=op, value = dest.value)
                            dest_node.append(op)
                        else:
                            counter += 1
                            op = op.split("+")[0]
                            op1 = op+"+"+str(counter)
                            multiInstance[op] = op1
                            if ddg_inst.opcode == "load":
                                sop =ddg_inst.input[0].operand
                                if sop in multiInstance.keys():
                                    sop = multiInstance[sop]
                                G.add_node(op1, len=itype, size=1, operand0=op1, pre=sop, value = dest.value)
                            else:
                                G.add_node(op1, len=itype, size=1, operand0=op1, value = dest.value)
                            dest_node.append(op1)
                else:
                    if op not in multiInstance.keys():
                        multiInstance[op] = op
                    else:
                        op = multiInstance[op]
                    if ddg_inst.opcode == "call":
                        if ddg_inst.funcname in funcMap.keys():
                            op_rep = funcMap[ddg_inst.funcname][ddg_inst.index(op) + 1]
                            rename_mapping[op_rep] = op
                        if "memcpy" in ddg_inst.funcname:
                            # if op not in G.nodes():
                            #    flag = 0
                            #    for node in G.nodes():
                            #        for i in range(int(G.node[node]['size'])):
                            #            if G.node[node]['operand'+str(i)] == op:
                            #                dest_node.append(node)
                            #                flag = 1
                            #                break
                            #    if flag == 0:
                            #        G.add_node(op, len=itype, size=1, operand0=op)
                            #        dest_node.append(op)
                            #else:
                            #    dest_node.append(op)
                            dest_address = memcpyRec[self.remap[idx]][0]
                            length = memcpyRec[self.remap[idx]][2]
                            for i in range(int(length)):
                                dest_new = str(int(dest_address) + i)
                                if dest_new in multiInstance.keys():
                                    dest_new = multiInstance[dest_new]
                                else:
                                    multiInstance[dest_new] = dest_new
                                if dest_new in G.nodes():
                                    counter = counter + 1
                                    G.add_node(dest_new+"+"+str(counter), len=itype, size=1, operand0="")
                                    multiInstance[dest_new] = dest_new+"+"+str(counter)
                                    dest_node.append(dest_new+"+"+str(counter))
                                else:
                                    G.add_node(dest_new, len=itype, size=1, operand0="")
                                    dest_node.append(dest_new)
                    else:
                        if op not in G.nodes():
                            if ddg_inst.opcode == "and" or ddg_inst.opcode == "or" or ddg_inst.opcode == "shl" or ddg_inst.opcode == "lshr" or ddg_inst.opcode == "ashr":
                                G.add_node(op, len=itype, size=1, operand0=op, bits=bitwiseRec[self.remap[idx]][2])
                                dest_node.append(op)
                            else:
                                G.add_node(op, len=itype, size=1, operand0=op, value = dest.value)
                                dest_node.append(op)
                        else:
                            counter += 1
                            op = op.split("+")[0]
                            op1 = op+"+"+str(counter)
                            multiInstance[op] = op1
                            G.add_node(op1, len=itype, size=1, operand0=op1, value = dest.value)
                            dest_node.append(op1)
            for s_node in source_node:
                for d_node in dest_node:
                    if "memcpy" in ddg_inst.funcname:
                        if source_node.index(s_node) == dest_node.index(d_node):
                            G.add_edge(s_node, d_node, opcode=ddg_inst.opcode)
                    else:
                        G.add_edge(s_node, d_node, opcode=ddg_inst.opcode)

            #print source_node
            #print dest_node
            #print "##############"
            totalbits += instbits
        print totalbits
        # have to hard-code the value of some nodes which are not assigned in the openmp part
        #G.node['.omp_microtask._%2']['value'] = 140733601624680
        #G.node['.omp_microtask._@wall']['value'] = 6328592
        #G.node['.omp_microtask._@cols']['value'] = 6328580
        #G.node['.omp_microtask._%2']['value'] = 140736750335664
        #G.node['.omp_microtask._@no_of_nodes']['value'] = 6320352
        G.node['.omp_microtask._%0']['value'] = 139702011644672
        G.node['.omp_microtask._%2']['value'] = 140737223074288
        G.node['.omp_microtask.1_%2']['value'] = 140737223074184
        G.node['.omp_microtask.1_%0']['value'] = 139702011644672
        return G


a = InstructionAbstraction.AbstractInst(config.indexFilePath, config.tracePath)
trace = a.export_trace()
ddg = DDG(trace)
G = ddg.ddg_construct(ddg.dynamic_trace, a.memcpyRec, a.bitwiseRec)
#nx.draw_random(G)
nx.write_dot(G, "./test.dot")
pvf_res = pvf.PVF(G, trace)
subG = pvf_res.computePVF(config.outputDataSet)
nx.nx.write_dot(subG, "./subgraph.dot")
#plt.show()