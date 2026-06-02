import cv2
import logging
from .model import FireModel

class InferencePipeline:
    def __init__(self, model_path="best.pt", confidence_threshold=0.5):
        self.model = FireModel(model_path)
        self.confidence_threshold = confidence_threshold
        self.class_names = self.model.get_names()
        
    def process_frame(self, frame):
        """
        Process a single frame and return detections.
        Returns a list of dicts: [{'class': name, 'confidence': conf, 'bbox': [x1, y1, x2, y2]}]
        """
        results = self.model.predict(frame, conf=self.confidence_threshold)
        detections = []
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # get class id
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                # get bounding box [x1, y1, x2, y2]
                xyxy = box.xyxy[0].tolist()
                
                # Assume standard names if mapping isn't fully set, or rely on model names
                cls_name = self.class_names.get(cls_id, str(cls_id))
                
                detections.append({
                    "class": cls_name,
                    "confidence": conf,
                    "bbox": xyxy
                })
        
        return detections

    def annotate_frame(self, frame, detections):
        """
        Draws bounding boxes and labels on the frame.
        """
        annotated_frame = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = map(int, det["bbox"])
            label = f'{det["class"]} {det["confidence"]:.2f}'
            
            # Choose color based on class (fire=red, smoke=gray/white)
            color = (0, 0, 255) if "fire" in det["class"].lower() else (200, 200, 200)
            
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated_frame, label, (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                        
        return annotated_frame
