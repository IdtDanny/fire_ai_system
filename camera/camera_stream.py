import cv2
import time
import logging

class CameraStream:
    def __init__(self, camera_index=0, width=640, height=480):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.cap = cv2.VideoCapture(self.camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        if not self.cap.isOpened():
            logging.error(f"Cannot open camera with index {self.camera_index}")
            raise Exception("Camera sequence failed to initialize.")
            
        logging.info(f"Camera initialized: {self.width}x{self.height} (index {self.camera_index})")

    def read_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            logging.warning("Failed to grab frame from camera.")
            return None
        return frame
        
    def release(self):
        self.cap.release()
        logging.info("Camera stream released.")

if __name__ == "__main__":
    # Test camera stream
    logging.basicConfig(level=logging.INFO)
    cam = CameraStream()
    try:
        while True:
            frame = cam.read_frame()
            if frame is not None:
                cv2.imshow('Camera Test (Press q to quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
