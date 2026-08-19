import cv2
import os
import glob

folder = "focus_test"  # Folder where your images are
images = glob.glob(f"{folder}/*.jpg")

results = []

print(f"{'Filename':<25} | {'Score':<10}")
print("-" * 40)

for img_path in images:
    image = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        continue
    variance = cv2.Laplacian(image, cv2.CV_64F).var()
    results.append((img_path, variance))

results.sort(key=lambda x: x[1], reverse=True)
for name, score in results:
    print(f"{os.path.basename(name):<25} | {score:.2f}")

print("-" * 40)
if results:
    print(f"WINNER: {results[0][0]} with score {results[0][1]:.2f}")
else:
    print(f"No readable JPG files found in '{folder}'.")
