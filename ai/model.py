from ultralytics import YOLO
import logging

class FireModel:
    def __init__(self, model_path="best.pt"):
        self.model_path = model_path
        self.model = None
        self.load_model()

    def load_model(self):
        try:
            # ultralytics YOLO will auto-download 'yolov8n.pt' if not found and requested
            self.model = YOLO(self.model_path)
            logging.info(f"YOLO model loaded from {self.model_path}")
        except Exception as e:
            logging.error(f"Failed to load YOLO model: {e}")
            raise e

    def predict(self, frame, conf=0.5):
        if self.model is None:
            logging.error("Model is not loaded.")
            return []
        
        # Run inference on the frame
        results = self.model.predict(frame, conf=conf, verbose=False)
        return results

    def get_names(self):
        return self.model.names if self.model else {}
