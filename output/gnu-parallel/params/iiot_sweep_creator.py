import pandas as pd

# Grid factors -------------------------------------------------------------
runs               = range(1, 11)                              # 1..10
typeTwoNStations   = [1] + list(range(10, 100, 10))            # 1, 10, 20, ..., 90
filterByBsr        = ["true", "false"]                          # ns-3 attribute string
maxTimeInList      = [32768, 57344, 106496, 204800]            # ~32, 57, 106, 204 ms (8192-multiples)
accessReqInterval  = [128, 256, 512, 1024, 1792]               # us

index = pd.MultiIndex.from_product(
    [runs, typeTwoNStations, filterByBsr, maxTimeInList, accessReqInterval],
    names=["run", "typeTwoNStations", "filterByBsr",
           "maxTimeInList", "accessReqInterval"],
)
base = pd.DataFrame(index=index).reset_index()

for name in ["a2p", "a2pv2"]:
    base.to_csv(f"{name}_iiot_input.csv", index=False)
    print(f"wrote {name}_iiot_input.csv  rows={len(base)}")
