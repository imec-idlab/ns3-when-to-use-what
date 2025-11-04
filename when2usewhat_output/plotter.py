import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

dplt_write_to = pd.DataFrame()

# --------------------
# UORA DATA COLLECTION
# --------------------
for ocw in [0, 1, 3, 7, 15, 31, 63]:
    for raRu in [0] + list(range(1, 10, 2)):
        dplt = pd.DataFrame()

        for runs in range(1, 7):
            for nsta in [1] + [z for z in range(20, 90, 20)] + [90]:
                file_path = f"uora_output_OCW{ocw}/{runs}_run-{nsta}_sta-{raRu}_rarus/per_sta_stats.out"
                if os.path.exists(file_path):
                    df_ap = pd.read_csv(file_path, delimiter="\t")
                else:
                    print(f"no file: {file_path}")
                    continue

                df_ap = df_ap[df_ap["MAC-addr"].isin(
                    [f"00:00:00:00:00:{9 + x:02x}" for x in range(1, nsta + 1)]
                )]
                df_ap.drop(columns=["MAC-addr", "SINR_dB", "RX_bytes"], inplace=True, errors='ignore')

                if not df_ap.empty:
                    df_ap["nSta"] = nsta
                    df_ap["Method"] = f"{raRu}"  # RA-RU count
                    df_ap["OCW"] = ocw
                    dplt = pd.concat([dplt, df_ap], ignore_index=True)

        if not dplt.empty:
            dplt_write_to = pd.concat([dplt_write_to, dplt], ignore_index=True)

# -------------------
# EDCA DATA COLLECTION
# -------------------
dplt_edca = pd.DataFrame()

for runs in range(1, 7):
    for nsta in [1]: # + [z for z in range(20, 90, 20)] + [90]:
        file_path = f"edca_output/{runs}_run-{nsta}_sta/per_sta_stats.out"
        if os.path.exists(file_path):
            df_ap = pd.read_csv(file_path, delimiter="\t")
        else:
            print(f"no file: {file_path}")
            continue

        df_ap = df_ap[df_ap["MAC-addr"].isin(
            [f"00:00:00:00:00:{9 + x:02x}" for x in range(1, nsta + 1)]
        )]
        df_ap.drop(columns=["MAC-addr", "SINR_dB", "RX_bytes"], inplace=True, errors='ignore')

        if not df_ap.empty:
            df_ap["nSta"] = nsta
            df_ap["Method"] = "edca"
            df_ap["OCW"] = -1
            dplt_edca = pd.concat([dplt_edca, df_ap], ignore_index=True)

# -------------------
# A2P DATA COLLECTION
# -------------------
dplt_a2p = pd.DataFrame()

for runs in range(1, 7):
    for nsta in [1] + [z for z in range(20, 70, 20)]:
        file_path = f"a2p_output_128/{runs}_run-{nsta}_sta/per_sta_stats.out"
        if os.path.exists(file_path):
            df_ap = pd.read_csv(file_path, delimiter="\t")
        else:
            print(f"no file: {file_path}")
            continue

        df_ap = df_ap[df_ap["MAC-addr"].isin(
            [f"00:00:00:00:00:{9 + x:02x}" for x in range(1, nsta + 1)]
        )]
        df_ap.drop(columns=["MAC-addr", "SINR_dB", "RX_bytes"], inplace=True, errors='ignore')

        if not df_ap.empty:
            df_ap["nSta"] = nsta
            df_ap["Method"] = "a2p"
            df_ap["OCW"] = -1
            dplt_a2p = pd.concat([dplt_a2p, df_ap], ignore_index=True)

# Merge EDCA & A2P into main dataset
dplt_write_to = pd.concat([dplt_write_to, dplt_edca, dplt_a2p], ignore_index=True)

# -------------------
# ANALYSIS & PLOTTING
# -------------------

if dplt_write_to.empty:
    print("No data to plot after merging!")
    exit()

# Filter out extreme values
filtered_all = dplt_write_to[dplt_write_to['Avg_delay_ms'] < 1550]

# Median delay per OCW/nSta/method
grouped = filtered_all.groupby(['nSta', 'Method', 'OCW'])['Avg_delay_ms'].median().reset_index()

# Get best OCW per nSta and Method (skip edca/a2p by using OCW = -1 directly)
best_combinations = pd.DataFrame()

ocw_methods = grouped[~grouped['Method'].isin(['edca', 'a2p'])]
idx = ocw_methods.groupby(['nSta', 'Method'])['Avg_delay_ms'].idxmin()
best_combinations = pd.concat([best_combinations, ocw_methods.loc[idx]])

# Include EDCA & A2P entries directly
best_combinations = pd.concat([
    best_combinations,
    grouped[grouped['Method'].isin(['edca', 'a2p'])]
], ignore_index=True)

# Filter original data based on best combinations
filtered_best_data = pd.merge(
    filtered_all,
    best_combinations[['nSta', 'Method', 'OCW']],
    on=['nSta', 'Method', 'OCW'],
    how='inner'
)

"""
# Filter only UORA methods (exclude EDCA and A2P)
uora_only_data = filtered_best_data[
    ~filtered_best_data["Method"].isin(["edca", "a2p"])
]
"""

# Plotting
plt.rcParams.update({
    'font.size': 15 })
"""
plt.rcParams.update({
    'font.size': 15,
    'axes.titlesize': 18,
    'axes.labelsize': 18,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'legend.fontsize': 12,
    'legend.title_fontsize': 12
})
"""
# Set order: 0, 1, 3, 5, 7, 9, edca, a2p
hue_order = ["a2p", "edca"] + [str(x) for x in [0, 1, 3, 5, 7, 9]]

# Map method to legend label
label_map = {str(x): "SA OFDMA" if x == 0 else "1 RA RU" if x == 1 else f"{x} RA RUs"
    for x in [0, 1, 3, 5, 7, 9]}
label_map["edca"] = "EDCA"
label_map["a2p"] = "A2P"

COMPRESS_FACTOR = 0.15
BOUND = 20
# Custom scale function
def custom_transform(y):
    """Stretch 0–15 linearly, compress >15 using a fixed factor."""
    if y <= BOUND:
        return y
    else:
        return BOUND + (y - BOUND) * COMPRESS_FACTOR  # compress factor: 0.2

def custom_inverse(y):
    """Inverse of custom_transform"""
    if y <= BOUND:
        return y
    else:
        return (y - BOUND) / COMPRESS_FACTOR + BOUND

# Apply the transformation to tick positions
def custom_ticks():
    base_ticks = [0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 30, 40, 50, 60]
    return [custom_transform(y) for y in base_ticks], base_ticks

#plt.figure(figsize=(10, 6))
plt.figure(figsize=(9.4, 6.8))
ax = plt.gca()

# Transform y data for plotting
filtered_best_data['y_transformed'] = filtered_best_data['Avg_delay_ms'].apply(custom_transform)

ax = sns.boxplot(x='nSta', y='y_transformed', hue='Method',
                 data=filtered_best_data, hue_order=hue_order, ax=ax,
                 showfliers=True,
                 whis=3.5,         # Less sensitive to outliers
                 width= .9         # Wider boxes

                )


# Set y-ticks and labels
tick_positions, tick_labels = custom_ticks()
ax.set_yticks(tick_positions)
ax.set_yticklabels([str(t) for t in tick_labels])

# Labels and legend
ax.set_ylabel("Average Delay (ms)")
ax.set_xlabel("Number of Stochastic STAs")
ax.grid(True, axis='y', linestyle='--', linewidth=0.5)
ax.grid(True, axis='x', linestyle='--', linewidth=0.5)

# Clean legend
handles, labels = ax.get_legend_handles_labels()
by_label = dict(zip(labels, handles))
new_labels = [label_map.get(label, label) for label in by_label.keys()]
ax.legend(by_label.values(), new_labels, loc=(.18, .47), prop={'size': 12}, title=None)

plt.tight_layout()



#plt.show()
#plt.savefig(f"fig3/Delay_paper.png") #, dpi=500)
