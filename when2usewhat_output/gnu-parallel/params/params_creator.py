import pandas as pd

run = range (1, 7)
nSta = [1] + [ z for z in range(10, 100, 10)]
nRaRus = [0] + [z for z in range(1, 10, 2)]
OCwMin = [0, 1, 3, 7, 15, 31, 63]

index = pd.MultiIndex.from_product([run, nSta], names = ["run", "nSta"])

pd.DataFrame(index = index).reset_index().to_csv(f"a2p_validation.csv", index=False)
