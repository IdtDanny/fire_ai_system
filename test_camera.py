import cv2
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"✅ Camera index {i} works! Frame shape: {frame.shape}")
        else:
            print(f"⚠️ Camera index {i} opened but could not read frame")
        cap.release()
    else:
        print(f"❌ Camera index {i} not available")