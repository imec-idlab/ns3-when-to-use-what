#!/usr/bin/python3

import json
import os
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
    df_downlink = pd.DataFrame()
    df_uplink = pd.DataFrame()
    df_roundtrip = pd.DataFrame()
    df_packetLoss = pd.DataFrame()
    for vars_line in list(product(*vars.values())):
        res_dir = '-'.join([str(x) for x in vars_line])
        nSta = vars_line[list(vars).index('nStations')]
        nRun = vars_line[list(vars).index('RngRun')]
        mcs = vars_line[list(vars).index('mcs')]
        # read AP file
        df_ul = pd.read_csv(f"{log_dir}/{res_dir}/00:00:00:00:00:"
                            f"{hex(nSta + 1)[2:].zfill(2)}",
                            delimiter="\t")

        # make a copy of the dataframe for uplink only
        df_ul_copy = df_ul.copy()
        # drop irrelevant columns
        df_ul_copy.drop(columns=["Generation_time", "Reception_time",
                                 "Received_from", "Packet_Tag"],
                        inplace=True, axis=1)
        # label as number of station
        df_ul_copy.insert(loc=0, column="nSta", value=pd.Series(
            [nSta for x in range(len(df_ul_copy.index))]))
        df_ul_copy.insert(loc=1, column="runs", value=pd.Series(
            [nRun for x in range(len(df_ul_copy.index))]))
        df_ul_copy.insert(loc=2, column="mcs", value=pd.Series(
            [mcs for x in range(len(df_ul_copy.index))]))

        df_uplink = pd.concat(
            [df_uplink, df_ul_copy], ignore_index=True)

        # drop irrelevant colums
        df_ul.drop(columns=["Reception_time", "Delay_ms"],
                   inplace=True, axis=1)

        df_pktLoss = pd.read_csv(f"{log_dir}/{res_dir}/per_sta_stats.out",
                                 delimiter="\t")

        # drop irrelevant colums
        df_pktLoss.drop(columns=["MAC-addr", "SINR_dB", "RX_bytes",
                                 "Avg_delay_ms"], inplace=True, axis=1)

        # add a few columns
        df_pktLoss.insert(loc=0, column="nSta", value=pd.Series(
            [nSta for x in range(len(df_pktLoss.index))]))
        df_pktLoss.insert(loc=1, column="runs", value=pd.Series(
            [nRun for x in range(len(df_pktLoss.index))]))
        df_pktLoss.insert(loc=2, column="mcs", value=pd.Series(
            [mcs for x in range(len(df_pktLoss.index))]))

        # concat to
        df_packetLoss = pd.concat([df_packetLoss, df_pktLoss],
                                  ignore_index=True)

        # dataframe per nSta
        df_dl_rt = pd.DataFrame()

        """
        # for loop
        """

        for node in range(1, nSta + 1):
            # read the file (STAs)
            df_dl = pd.read_csv(f"{log_dir}/{res_dir}/00:00:00:00:00:"
                                f"{hex(node)[2:].zfill(2)}",
                                delimiter="\t")

            # make a copy
            df_dl_copy = df_dl.copy()
            # drop *irrelevant colums
            df_dl_copy.drop(
                columns=["Received_from", "Generation_time",
                         "Reception_time", "Packet_Tag"], inplace=True, axis=1)

            df_dl.drop(columns=["Received_from", "Generation_time",
                                "Delay_ms"], inplace=True, axis=1)

            df_dl_copy.insert(loc=0, column="nSta", value=pd.Series(
                [nSta for x in range(len(df_dl_copy.index))]))
            df_dl_copy.insert(loc=1, column="runs", value=pd.Series(
                [nRun for x in range(len(df_dl_copy.index))]))
            df_dl_copy.insert(loc=2, column="mcs", value=pd.Series(
                [mcs for x in range(len(df_dl_copy.index))]))

            df_downlink = pd.concat([df_downlink, df_dl_copy],
                                    ignore_index=True)

            # Refill/recreate Received_from, populate with the mac of
            # sta. Needed for inner join
            df_dl["Received_from"] = pd.Series(
                ["00:00:00:00:00:{sta_node}".format(sta_node=hex(node)[2:]
                                                    .zfill(2))
                 for x in range(len(df_dl.index))])

            # Inner join on 'Received_from', 'Packet_Tag'
            df_merged = pd.merge(
                df_dl, df_ul, how='inner',
                on=['Received_from', 'Packet_Tag'])

            # Create a roundtrip delay column
            df_merged["round_trip_time"] = pd.Series(
                df_merged['Reception_time'] - df_merged['Generation_time'])

            # append the two dataframes
            df_dl_rt = pd.concat([df_dl_rt, df_merged], ignore_index=True)

        df_dl_rt.insert(loc=0, column="nSta", value=pd.Series(
            [nSta for x in range(len(df_dl_rt.index))]))
        df_dl_rt.insert(loc=1, column="runs", value=pd.Series(
            [nRun for x in range(len(df_dl_rt.index))]))
        df_dl_rt.insert(loc=2, column="mcs", value=pd.Series(
            [mcs for x in range(len(df_dl_rt.index))]))

        df_roundtrip = pd.concat([df_roundtrip, df_dl_rt], ignore_index=True)

    # take our unnecessary columns

    df_roundtrip.drop(columns=["Reception_time", "Received_from",
                               "Generation_time", "Packet_Tag"],
                      inplace=True, axis=1)
    # average base on the invidual runs
    grouped = df_roundtrip.groupby(['mcs', 'runs', 'nSta'], as_index=False
                                   )['round_trip_time'].mean()

    # prepare the dataframe to write to output
    gr = grouped.reset_index()[['mcs', 'runs', 'nSta',
                                'round_trip_time']]

    gr.rename(columns={'round_trip_time': 'avg_rtt'}, inplace=True)

    gr.drop(columns=['runs'], inplace=True, axis=1)

    df_to_write = gr.groupby(['mcs', 'nSta'], as_index=False)[
        'avg_rtt'].mean().reset_index()[['mcs', 'nSta', 'avg_rtt']]

    df_to_write['std_rtt'] = gr.groupby(['mcs', 'nSta'], as_index=False)[
        'avg_rtt'].std()['avg_rtt']

    # rtt percentile
    gr = df_roundtrip.groupby(
        ['mcs', 'runs', 'nSta'], as_index=False)[
            'round_trip_time'].quantile(q=.99).reset_index()[
        ['mcs', 'runs', 'nSta', 'round_trip_time']]
    gr.drop(columns=['runs'], inplace=True, axis=1)

    df_to_write['percent_rtt'] = gr.groupby(
        ['mcs', 'nSta'], as_index=False)['round_trip_time'].quantile(
        q=.99)['round_trip_time']

    # downlink

    gr = df_downlink.groupby(
        ['mcs', 'runs', 'nSta'], as_index=False)[
            'Delay_ms'].mean().reset_index()[
        ['mcs', 'runs', 'nSta', 'Delay_ms']]
    gr.drop(columns=['runs'], inplace=True, axis=1)
    df_to_write['avg_dl'] = gr.groupby(
        ['mcs', 'nSta'], as_index=False)['Delay_ms'].mean()['Delay_ms']
    df_to_write['std_dl'] = gr.groupby(
        ['mcs', 'nSta'], as_index=False)['Delay_ms'].std()['Delay_ms']

    gr = df_downlink.groupby(
        ['mcs', 'runs', 'nSta'], as_index=False)[
            'Delay_ms'].quantile(q=.99).reset_index()[
        ['mcs', 'runs', 'nSta', 'Delay_ms']]
    gr.drop(columns=['runs'], inplace=True, axis=1)
    df_to_write['percent_dl'] = gr.groupby(
        ['mcs', 'nSta'], as_index=False)['Delay_ms'].quantile(
        q=.99)['Delay_ms']

    # uplink

    gr = df_uplink.groupby(
        ['mcs', 'runs', 'nSta'], as_index=False)[
            'Delay_ms'].mean().reset_index()[
        ['mcs', 'runs', 'nSta', 'Delay_ms']]
    gr.drop(columns=['runs'], inplace=True, axis=1)
    df_to_write['avg_ul'] = gr.groupby(
        ['mcs', 'nSta'], as_index=False)['Delay_ms'].mean()['Delay_ms']
    df_to_write['std_ul'] = gr.groupby(
        ['mcs', 'nSta'], as_index=False)['Delay_ms'].std()['Delay_ms']

    gr = df_uplink.groupby(
        ['mcs', 'runs', 'nSta'], as_index=False)[
            'Delay_ms'].quantile(q=.99).reset_index()[
        ['mcs', 'runs', 'nSta', 'Delay_ms']]
    gr.drop(columns=['runs'], inplace=True, axis=1)
    df_to_write['percent_ul'] = gr.groupby(
        ['mcs', 'nSta'], as_index=False)['Delay_ms'].quantile(
        q=.99)['Delay_ms']

    # packet loss rate

    gr = df_packetLoss.groupby(
        ['mcs', 'runs', 'nSta'], as_index=False)[
            'Packet_loss_ratio'].quantile(q=.99).reset_index()[
        ['mcs', 'runs', 'nSta', 'Packet_loss_ratio']]
    gr.drop(columns=['runs'], inplace=True, axis=1)
    df_to_write['percent_pkt_loss'] = gr.groupby(
        ['mcs', 'nSta'], as_index=False)['Packet_loss_ratio'].quantile(
        q=.99)['Packet_loss_ratio']

    print(f'\n{df_to_write}')

    df_to_write.to_csv("preped_output.csv", index=False)


#        plot_mean(df_roundtrip, "Number of STAs", "Average Delay (ms)",
#                  "Avg Delay vrs Num of Devices",
#                  f"{output_label}_roundtrip_Avg_mcs_{start_mcs}_"
#                  f"{stop_mcs}.png", "round_trip_time", mcs,
#                  plt.figure(1))
#        plot_percentile(df_roundtrip, "Number of STAs",
#                        "Latency (ms) - 99 percentile",
#                        "Latency vrs Num of Devices",
#                        f"{output_label}_roundtrip_percentile_mcs_{start_mcs}"
#                        f"_{stop_mcs}.png", "round_trip_time", mcs,
#                        plt.figure(2))
#        plot_mean(df_uplink, "Number of STAs", "Average Delay (ms)",
#                  "Avg Delay vrs Num of Devices - UL",
#                  f"{output_label}_uplink_Avg_mcs_{start_mcs}_{stop_mcs}.png",
#                  "Delay_ms", mcs, plt.figure(3))
#        plot_percentile(df_uplink, "Number of STAs",
#                        "Latency (ms) - 99 percentile",
#                        "Latency vrs Num of Devices - UL",
#                        f"{output_label}_uplink_percentile_mcs_{start_mcs}_"
#                        f"{stop_mcs}.png", "Delay_ms", mcs, plt.figure(4))
#        plot_mean(df_downlink, "Number of STAs", "Average Delay (ms)",
#                  "Avg Delay vrs Num of Devices - DL",
#                  f"{output_label}_downlink_Avg_mcs_{start_mcs}_"
#                  f"{stop_mcs}.png", "Delay_ms", mcs, plt.figure(5))
#        plot_percentile(df_downlink, "Number of STAs",
#                        "Latency (ms) - 99 percentile",
#                        "Latency vrs Num of Devices - DL",
#                        f"{output_label}_downlink_percentile_mcs_{start_mcs}_"
#                        f"{stop_mcs}.png", "Delay_ms", mcs, plt.figure(6))
#
#        plot_percentile(df_packetLoss, "Number of STAs",
#                        "Latency (ms) - 99 percentile",
#                        "Packet Loss Ratio vrs Num of Device",
#                        f"{output_label}_Packet_Loss_Ratio_mcs_{start_mcs}_"
#                        f"{stop_mcs}.png", "Packet_loss_ratio", mcs,
#                        plt.figure(7))


def generate_run_string(cfg) -> str:
    cmd = ("./../../ns3 run --no-build 'scratch/wifi-ax-veloce/wifi-ax-veloce "
           f"--simulationTime={cfg['CONSTANTS']['simulationTime']} "
           f"--accessCategory={cfg['CONSTANTS']['accessCategory']} "
           f"--phyModel={cfg['CONSTANTS']['phyModel']} "
           f"--channelWidth={cfg['CONSTANTS']['channelWidth']} "
           f"--dlAckType={cfg['CONSTANTS']['dlAckType']} "
           f"--enableUlOfdma={cfg['CONSTANTS']['enableUlOfdma']} "
           f"--enableBsrp={cfg['CONSTANTS']['enableBsrp']} "
           f"--useRts={cfg['CONSTANTS']['useRts']} "
           f"--ulPayloadSize={cfg['CONSTANTS']['ulPayloadSize']} "
           f"--dlPayloadSize={cfg['CONSTANTS']['dlPayloadSize']} "
           f"--interval={cfg['CONSTANTS']['interval']} "
           f"--maxDistance={cfg['CONSTANTS']['maxDistance']} "
           f"--useMuEdca={cfg['CONSTANTS']['useMuEdca']} "
           f"--muSchedAccessReqInterval={cfg['CONSTANTS']['AccReqInterval']} "
           f"--txPowerStart={cfg['CONSTANTS']['txPowerStart']} "
           f"--txPowerEnd={cfg['CONSTANTS']['txPowerEnd']} "
           f"--UseCentral26TonesRus={cfg['CONSTANTS']['Central26TonesRus']} "
           f"--StartSendInterval={cfg['CONSTANTS']['StartSendInterval']} "
           f"--startLogTime={cfg['CONSTANTS']['startLogTime']} "
           f"--DelayAccessReqUponAccess={cfg['CONSTANTS']['DelayAccessReq']} "
           f"--strictWindow={cfg['CONSTANTS']['strictWindow']} "
           f"--nMpdus={cfg['CONSTANTS']['nMpdus']} "
           f"--nMsdus={cfg['CONSTANTS']['nMsdus']} "
           f"--enableAggregation={cfg['CONSTANTS']['enableAggregation']} "
           f"--logDir={os.getcwd()}/{cfg['CONSTANTS']['outputFolder']}/$"
           f"{'-$'.join ([x for x in cfg['VARIABLES'].keys()])} "
           "--RngRun=${} --nStations=${} --mcs=${} --TxOPLimits=${}'".format(
               *cfg['VARIABLES'].keys()))

    return cmd


def run_locally(cfg_data):
    cmd = generate_run_string(cfg_data)
    for keys in cfg_data['VARIABLES'].keys():
        cmd = cmd.replace("$" + keys, "{}")

    for var in list(product(*cfg_data['VARIABLES'].values())):
        to_run = cmd.format(*(var * 2))
        output = os.system(to_run)
        print("Output:", output)


if __name__ == '__main__':
    with open("config_file.json") as config:
        cfg_data = json.load(config)

    if cfg_data['COMMANDS']['runLocally'] == 'true':
        run_locally(cfg_data)
    elif cfg_data['COMMANDS']['prep_data'] == 'true':
        data_prep(cfg_data['VARIABLES'], cfg_data['CONSTANTS']['outputFolder'])
