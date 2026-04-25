import os


#run this file to combine parts to a single zip file
folder = ""



files = [
    os.path.join(folder, f)
    for f in os.listdir(folder)
    if os.path.isfile(os.path.join(folder, f))
]

print(files)


with open(files[0]+".zip", "wb") as out:
    for p in files:
        with open(p, "rb") as f:
            out.write(f.read())
