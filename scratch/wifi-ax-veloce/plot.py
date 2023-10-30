#!/usr/bin/python3

import json
import pandas as pd
import matplotlib.pyplot as plt

from itertools import product

def plot_percentile(data: pd.DataFrame(), xlabel: str, ylabel: str, title: str,
                    file_name: str, y_clmn_name: str, mcs: int,
                    fig: plt.Figure):

    df_percentile = data.groupby('nSta', as_index=False).quantile(q=.99)

    plt.plot(df_percentile["nSta"], df_percentile[y_clmn_name],
             linestyle='dashed', linewidth=2, marker='o', markersize=5,
             label="mcs-{mcs}".format(mcs=mcs))

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True)
    plt.title(title)
    plt.savefig(file_name, dpi=500)


def plot_mean(data: pd.DataFrame(), xlabel: str, ylabel: str, title: str,
              file_name: str, y_clmn_name: str, mcs: int,
              fig: plt.Figure):

    df_mean = data.groupby('nSta', as_index=False).mean()
    df_std = data.groupby('nSta', as_index=False).std()

    plt.errorbar(df_mean["nSta"], df_mean[y_clmn_name],
                 yerr=df_std[y_clmn_name], fmt='-o', capsize=5,
                 label="mcs-{mcs}".format(mcs=mcs))

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True)
    plt.title(title)
    plt.savefig(file_name, dpi=500)


def data_prep(vars: dict, log_dir: str):
    for vars_line in list(product(*vars.values())):
        res_dir = '-'.join ([str(x) for x in vars_line])
        nStas = vars_line[list(vars).index ('nStations')]
        for nSta in range(0, nStas):
            df_ul = pd.read_csv(f"{log_dir}"
                    f"/{res_dir}"
                    f"/00:00:00:00:00:{hex(nSta + 1)[2:].zfill(2)}",
                    delimiter="\t"
                    )
            print (df_ul)

    #for mcs in range(start_mcs, stop_mcs + 1):
    #    df_downlink = pd.DataFrame()
    #    df_uplink = pd.DataFrame()
    #    df_roundtrip = pd.DataFrame()
    #    df_packetLoss = pd.DataFrame()
    #    for runs in range(start_run, stop_run + 1):
    #        for nSta in range(start_nSta, stop_nSta + 1):
    #            # read the file (AP)
    #            df_ul = pd.read_csv(f"{output}"
    #                                f"/00:00:00:00:00:{hex(nSta + 1)[2:].zfill(2)}",
    #                                delimiter="\t"
    #                                )
    #            # make a copy of the dataframe for uplink only
    #            df_ul_copy = df_ul.copy()
    #            # drop irrelevant columns
    #            df_ul_copy.drop(columns=["Generation_time", "Reception_time",
    #                                     "Received_from", "Packet_Tag"],
    #                            inplace=True, axis=1
    #                            )

    #            # label as number of station
    #            df_ul_copy["nSta"] = pd.Series(
    #                [nSta for x in range(len(df_ul_copy.index))])

    #            df_uplink = pd.concat(
    #                [df_uplink, df_ul_copy], ignore_index=True)

    #            # drop irrelevant colums
    #            df_ul.drop(columns=["Reception_time", "Delay_ms"],
    #                       inplace=True, axis=1
    #                       )

    #            df_pktLoss = pd.read_csv("{pdir}/{runs}run-{nSta}"
    #                                     "nStations-mcs{mcs}/per_sta_stats.out"
    #                                     .format(runs=runs, nSta=nSta,
    #                                             pdir=parent_dir, mcs=mcs),
    #                                     delimiter="\t")

    #            # drop irrelevant colums
    #            df_pktLoss.drop(columns=["MAC-addr", "SINR_dB", "RX_bytes",
    #                                     "Avg_delay_ms"], inplace=True, axis=1)

    #            # label as number of station
    #            df_pktLoss["nSta"] = pd.Series(
    #                [nSta for x in range(len(df_pktLoss.index))])

    #            # concat to
    #            df_packetLoss = pd.concat([df_packetLoss, df_pktLoss],
    #                                      ignore_index=True)

    #            # dataframe per nSta
    #            df_dl = pd.DataFrame()

    #            """
    #            # for loop
    #            """

    #            for node in range(1, nSta + 1):
    #                # read the file (STAs)
    #                df_dl = pd.read_csv(
    #                    "{pdir}/{runs}run-{nSta}nStations-mcs"
    #                    "{mcs}/00:00:00:00:00:{sta_node}"
    #                    .format(runs=runs, nSta=nSta, mcs=mcs,
    #                            pdir=parent_dir,
    #                            sta_node=hex(node)[2:].zfill(2)),
    #                    delimiter="\t")
    #                # make a copy
    #                df_dl_copy = df_dl.copy()
    #                # drop *irrelevant colums
    #                df_dl_copy.drop(
    #                    columns=["Received_from", "Generation_time",
    #                             "Reception_time", "Packet_Tag"], inplace=True,
    #                    axis=1)
    #                df_dl.drop(columns=["Received_from", "Generation_time",
    #                                    "Delay_ms"], inplace=True, axis=1)

    #                df_dl_copy["nSta"] = pd.Series(
    #                    [nSta for x in range(len(df_dl_copy.index))])

    #                df_downlink = pd.concat([df_downlink, df_dl_copy],
    #                                        ignore_index=True)

    #                # Refill/recreate Received_from, populate with the mac of
    #                # sta. Needed for inner join
    #                df_dl["Received_from"] = pd.Series(
    #                    ["00:00:00:00:00:{sta_node}"
    #                     .format(sta_node=hex(node)[2:].zfill(2))
    #                     for x in range(len(df_dl.index))])

    #                # Inner join on 'Received_from', 'Packet_Tag'
    #                df_merged = pd.merge(
    #                    df_dl, df_ul, how='inner',
    #                    on=['Received_from', 'Packet_Tag'])

    #                # Create a roundtrip delay column
    #                df_merged["round_trip_time"] = pd.Series(
    #                    df_merged['Reception_time'] - df_merged[
    #                        'Generation_time'])

    #                # append the two dataframes
    #                df_dl = pd.concat([df_dl, df_merged], ignore_index=True)

    #            df_dl["nSta"] = pd.Series(
    #                [nSta for x in range(len(df_dl.index))])

    #            df_roundtrip = pd.concat([df_roundtrip, df_dl],
    #                                     ignore_index=True)
    #    df_roundtrip.drop(columns=["Reception_time", "Received_from",
    #                               "Generation_time", "Packet_Tag"],
    #                      inplace=True, axis=1)

    #    plot_mean(df_roundtrip, "Number of STAs", "Average Delay (ms)",
    #              "Avg Delay vrs Num of Devices",
    #              f"{output_label}_roundtrip_Avg_mcs_{start_mcs}_"
    #              f"{stop_mcs}.png", "round_trip_time", mcs,
    #              plt.figure(1))
    #    plot_percentile(df_roundtrip, "Number of STAs",
    #                    "Latency (ms) - 99 percentile",
    #                    "Latency vrs Num of Devices",
    #                    f"{output_label}_roundtrip_percentile_mcs_{start_mcs}"
    #                    f"_{stop_mcs}.png", "round_trip_time", mcs,
    #                    plt.figure(2))
    #    plot_mean(df_uplink, "Number of STAs", "Average Delay (ms)",
    #              "Avg Delay vrs Num of Devices - UL",
    #              f"{output_label}_uplink_Avg_mcs_{start_mcs}_{stop_mcs}.png",
    #              "Delay_ms", mcs, plt.figure(3))
    #    plot_percentile(df_uplink, "Number of STAs",
    #                    "Latency (ms) - 99 percentile",
    #                    "Latency vrs Num of Devices - UL",
    #                    f"{output_label}_uplink_percentile_mcs_{start_mcs}_"
    #                    f"{stop_mcs}.png", "Delay_ms", mcs, plt.figure(4))
    #    plot_mean(df_downlink, "Number of STAs", "Average Delay (ms)",
    #              "Avg Delay vrs Num of Devices - DL",
    #              f"{output_label}_downlink_Avg_mcs_{start_mcs}_"
    #              f"{stop_mcs}.png", "Delay_ms", mcs, plt.figure(5))
    #    plot_percentile(df_downlink, "Number of STAs",
    #                    "Latency (ms) - 99 percentile",
    #                    "Latency vrs Num of Devices - DL",
    #                    f"{output_label}_downlink_percentile_mcs_{start_mcs}_"
    #                    f"{stop_mcs}.png", "Delay_ms", mcs, plt.figure(6))

    #    plot_percentile(df_packetLoss, "Number of STAs",
    #                    "Latency (ms) - 99 percentile",
    #                    "Packet Loss Ratio vrs Num of Device",
    #                    f"{output_label}_Packet_Loss_Ratio_mcs_{start_mcs}_"
    #                    f"{stop_mcs}.png", "Packet_loss_ratio", mcs,
    #                    plt.figure(7))


if __name__ == '__main__':
    with open("config_file.json") as config:
        cfg_data = json.load(config)
        
    #print (cfg_data['VARIABLES'], cfg_data['CONSTANTS']['outputFolder'])

    data_prep(cfg_data['VARIABLES'], cfg_data['CONSTANTS']['outputFolder'])
