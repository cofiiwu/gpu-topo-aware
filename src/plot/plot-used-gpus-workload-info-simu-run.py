# # !/usr/bin/python
# # -*- coding: utf-8 -*-
# #
# # simu-plot -- Plot a workload schedule
# #
# # Given a system configuration, a workload description, and a schedule as
# # generated by simulation, this program generates a plot displaying the
# # amount of gpus used by each job over time, as well as submission times
# # for each job in the workload.
# #
# # Copyright © 2017 Marcelo Amaral <marcelo.amaral@bsc.es>
#

import os
import copy
import json
import math
import argparse
import itertools
import configparser
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

import numpy as np
import seaborn as sns


def workloads_exec_time_add_value(workload_list, name, job, gpus_list, start_time, end_time, submitted_time):
    if name not in workload_list:
        workload_list[name] = dict()
    if job not in workload_list[name]:
        workload_list[name][job] = dict()
        exec_time = end_time - start_time
        exec_time_submitted = end_time - submitted_time

        workload_list[name][job]['gpus'] = gpus_list
        workload_list[name][job]['start_time'] = start_time
        workload_list[name][job]['end_time'] = end_time
        workload_list[name][job]['submitted_time'] = submitted_time
        workload_list[name][job]['exec_time'] = exec_time
        workload_list[name][job]['exec_time_submitted'] = exec_time_submitted
    return workload_list


def get_fig_index():
    return itertools.cycle(['(c)', '(d)', '(b)', '(a)', '(e)', '(f)', '(g)', '(h)'])


def get_colors():
    return itertools.cycle(['k', 'g', 'r', 'b', 'm', 'y', 'c'])


def get_lines_format():
    return itertools.cycle(["--", "-.", ":", "-"])


def get_colors2():
    return itertools.cycle(['#f2b1bc', '#02e0bd', '#7cc8f0', '#9083de', '#07a998', '#5a71ff', '#224fc2', '#19f2fb',
                            '#8e9e1f', '#3266c8', '#2b2c08', '#975ce0', '#e1c295', '#95e4c9', '#5d160e', '#4b5241',
                            '#7a55f8', '#ac3320', '#58aa2d', '#953164'])


def get_pattern():
    return itertools.cycle(['/', 'o', 'x', '-', '+', 'O', '.', '*'])


folders = list()
for root, directories, files in os.walk("../../results/"):
    if not "real" in root and not "600" in root:
        if 'placement_stats.json' in files:
            print "folder: ", root, files
            folders.append(root + "/")

sys_config = configparser.ConfigParser(delimiters=("="))
sys_config.read("../../etc/configs/sys-config.ini")

job_profiles = json.load(
                open("../../data/profiles/" + json.loads(sys_config.get("workload", "profile")) + ".json", "r"))


length = sys_config.getfloat("simulator", "length")
period = sys_config.getfloat("simulator", "period")
digits = sys_config.getint("simulator", "digits")
window_min = sys_config.getfloat("plot", "window_min")
window_max = sys_config.getfloat("plot", "window_max")
submissions = sys_config.getboolean("plot", "submissions")
workload_file = json.loads(sys_config.get("workload", "workload_file"))
offset = int(math.floor(window_min / period))

workloads_exec_time = dict()
ap = argparse.ArgumentParser()
ap.add_argument("-c", "--sched_config", dest="c", required=False,
                help="System configuration file", default="../../etc/configs/sched_config-")
ap.add_argument("-w", "--workload", dest="w", required=False,
                help="JSON workload file", default="../../data/")
ap.add_argument("-s", "--schedule", dest="s", required=False,
                help="JSON schedule file", default="sched_stats.json")
ap.add_argument("-p", "--placement", dest="p", required=False,
                help="JSON schedule file", default="placement_stats.json")
ap.add_argument("-t", "--stats", dest="t", required=False,
                help="JSON stats file", default="system_stats.json")
args = ap.parse_args()

with open(args.w + workload_file + ".json") as w:
    workload = json.load(w)

sns.set_context("paper", font_scale=3)

fig_indexs = get_fig_index()
postponded = False
num_gpus = 0

for result_folder in folders:
    # result_folder = folders[0]
    lines_format = get_lines_format()
    colors = get_colors()
    patterns = get_pattern()
    values = result_folder.split("/")
    algo_name = values[5].split("-")

    if not postponded:
        if "bf" in algo_name:
            folders.append(result_folder)
            postponded = True

    # print algo_name
    if "utilityaware" not in algo_name:
        algo_name = algo_name[len(algo_name) - 1].upper()
    else:
        postpone = algo_name[len(algo_name) - 1]
        algo_name = algo_name[len(algo_name) - 5].upper()
        if postpone == 'True':
            algo_name += "-P"

    args = ap.parse_args()
    sched_config = configparser.ConfigParser(delimiters=("="))
    sched_config.read(args.c + algo_name + '.ini')

    args = ap.parse_args()

    with open(result_folder+args.s) as s:
        scheduler_stats = json.load(s)

    with open(result_folder+args.p) as p:
        placement_stats = json.load(p)

    with open(result_folder+args.t) as t:
        system_stats = json.load(t)

    jobs = workload
    steps = dict()
    for s, v in placement_stats.iteritems():
        steps[int(float(s))] = s
    steps = sorted(steps.iteritems(), key=lambda t: t[0], reverse=False)
    x = np.array(steps)

    ordered_jobs = []
    for job in jobs:
        ordered_jobs.append(int(job))
    ordered_jobs = sorted(ordered_jobs)

    running_job = dict()
    running_time = dict()
    num_used_gpus = dict()
    num_requested_gpus = dict()

    steps2 = np.zeros(int(window_max), dtype=np.int)
    for step in range(int(window_max)):
        running_time[step] = dict()

    added = list()
    for step, k in enumerate(steps):
        k_str = k[1]
        k = k[0]
        if k_str not in placement_stats:
            continue

        for jid in ordered_jobs:
            jid = str(jid)

            if jid in placement_stats[k_str]:
                submitted = float(placement_stats[k_str][jid]["submitted_time"])
                start = float(placement_stats[k_str][jid]["start_time"])
                if placement_stats[k_str][jid]["end_time"] is not None:
                    end = float(placement_stats[k_str][jid]["end_time"])
                else:
                    end = 0
                gpus_list = placement_stats[k_str][jid]["gpus"]
                arrival_time = workload[str(jid)]["arrival"]

                if (k >= arrival_time) and (k <= start):
                    if k in num_requested_gpus:
                        num_requested_gpus[step] += len(gpus_list)
                    else:
                        num_requested_gpus[step] = len(gpus_list)

                if (k >= start) and (k <= end):
                    if k in num_requested_gpus:
                        num_used_gpus[step] += len(gpus_list)
                    else:
                        num_used_gpus[step] = len(gpus_list)

                if jid not in running_job:
                    running_job[jid] = np.zeros(len(steps2), dtype=np.int)

                for i in range(int(start), int(end)):
                    running_job[jid][i] = len(gpus_list)
                    if jid not in running_time[i]:
                        running_time[i] = dict()
                    running_time[i][jid] = len(gpus_list)

    # accumulate running gpus to plot stepped figure
    arunning = copy.deepcopy(running_job)
    for step, k_str in enumerate(steps2):
        for m, i in enumerate(ordered_jobs):
            jid = str(i)
            if jid in running_time[step]:
                for n, j in enumerate(ordered_jobs):
                    if jid != j:
                        if j in running_time[step]:
                            arunning[jid][step] += running_job[str(j)][step]

    df = pd.DataFrame(arunning)
    ax = df.plot(kind='area', linewidth=0.0, legend=False)
    for i, j in arunning.iteritems():
        print i, np.array(j).max()

    ax.set_ylabel('# Requested GPUs', alpha=0.8, fontsize=34)
    ax.set_xlabel('Time(s)', alpha=0.8, fontsize=34)
    plt.show()
    break