import os
import matplotlib.pyplot as plt
import numpy as np
import math
import matplotlib
from numpy import mean, median

def data_extract(dir_root = "/home/diwu/Project/UnarySim/app/uBrain/hw/systolic_array/result/",
    run_prefix = "eyeriss_08b_bp_001c_uBrain_t",
    run_postfix = "_ddr3_w__spm",
    total_timestamp = 10):

    sample_freq = 128
    area_list = []
    runtime_list = []
    freq_list = []
    energy_list = []
    energy_delay_prod_list = []
    energy_eff_list = []
    power_list = []
    power_eff_list = []

    for t in range(total_timestamp):
        run_name = run_prefix+str(t)+run_postfix
        run_dir = dir_root + run_name + "/"
        # print("Processing dir: " + dir_root + run_name)

        area_file = run_dir + "simEffOut/" + run_name + "_area.csv"
        throughput_file = run_dir + "simHwOut/" + run_name + "_throughput_real.csv"
        energy_file = run_dir + "simEffOut/" + run_name + "_energy.csv"
        power_file = run_dir + "simEffOut/" + run_name + "_power.csv"
    
        if t == 0:
            area_list.append(return_indexed_elems(input_csv=area_file, index=0)[-1]) # dram area
            area_list.append(return_indexed_elems(input_csv=area_file, index=8)[-1]) # sram area
            area_list.append(return_indexed_elems(input_csv=area_file, index=13)[-1]) # sa area
            area_list.append(return_indexed_elems(input_csv=area_file, index=14)[-1]) # total area

        runtime_list.append(return_indexed_elems(input_csv=throughput_file, index=3)[-1]) # total real runtime

        cycle = return_indexed_elems(input_csv=throughput_file, index=2)[-1]
        freq = 1 / ((t + 1) / sample_freq / cycle)
        freq_list.append(freq)

        energy_list_temp = []
        energy_list_temp.append(return_indexed_elems(input_csv=energy_file, index=8)[-1]) # dram energy
        energy_list_temp.append(return_indexed_elems(input_csv=energy_file, index=18)[-1]) # sram energy
        energy_list_temp.append(return_indexed_elems(input_csv=energy_file, index=33)[-1]) # sa energy
        energy_list_temp.append(return_indexed_elems(input_csv=energy_file, index=36)[-1]) # total energy
        energy_list.append(energy_list_temp)
        # energy_delay_prod_list.append([e * runtime_list[-1][-1] for e in energy_list_temp])
        # energy_eff_list.append([e/runtime_list[-1][-1] for e in energy_list_temp])

        power_list_temp = []
        power_list_temp.append(return_indexed_elems(input_csv=power_file, index=8)[-1]) # dram power
        power_list_temp.append(return_indexed_elems(input_csv=power_file, index=18)[-1]) # sram power
        power_list_temp.append(return_indexed_elems(input_csv=power_file, index=33)[-1]) # sa power
        power_list_temp.append(return_indexed_elems(input_csv=power_file, index=36)[-1]) # total power
        power_list.append(power_list_temp)
        # power_eff_list.append([p/runtime_list[-1][-1] for p in power_list_temp])

    area_list = area_list # mm^2
    runtime_list = [freq * 1000. for freq in runtime_list] # ms
    freq_list = [freq / 1000000. for freq in freq_list] # MHz
    power_list = power_list # mW
    energy_list = energy_list # nJ

    return area_list, runtime_list, freq_list, power_list


def prune(input_list):
    l = []

    for e in input_list:
        e = e.strip() # remove the leading and trailing characters, here space
        if e != '' and e != ' ':
            l.append(e)

    return l


def return_indexed_elems(input_csv=None, index=None):
    l = []

    csv_file = open(input_csv, "r")
    
    first = True
    for entry in csv_file:
        if first == True:
            first = False
            continue

        elems = entry.strip().split(',')
        elems = prune(elems)
        if len(elems) > 0:
            l.append(float(elems[index]))
    
    csv_file.close()

    return l


if __name__ == '__main__':
    area_list, runtime_list, freq_list, power_list = data_extract(dir_root = "/home/diwu/Project/UnarySim/app/uBrain/hw/systolic_array/result/",
    run_prefix = "eyeriss_08b_bp_001c_uBrain_t",
    run_postfix = "_ddr3_w__spm",
    total_timestamp = 10)

    print(area_list)
    print(runtime_list)
    print(freq_list)
    print(power_list)

