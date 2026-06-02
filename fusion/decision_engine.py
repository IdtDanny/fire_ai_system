import logging
from config import CONFIG

class DecisionEngine:
    def __init__(self, temp_threshold=CONFIG["TEMP_THRESHOLD"], gas_threshold=CONFIG["GAS_THRESHOLD"], fire_conf_threshold=CONFIG["CONFIDENCE_THRESHOLD"], high_fire_conf=CONFIG["HIGH_FIRE_CONF"]):
        self.temp_threshold = temp_threshold
        self.gas_threshold = gas_threshold
        self.fire_conf_threshold = fire_conf_threshold
        self.high_fire_conf = high_fire_conf

    def evaluate(self, detections, temperature, gas_value):
        """
        Evaluate inputs and decide actions based on rule set.
        detections: List of dicts from InferencePipeline
        temperature: Current temperature or moving average
        gas_value: Current gas sensor analog value
        
        Returns integer enum:
        0 - Normal
        1 - Alert (minor detection, needs attention)
        2 - Suppression (definite fire confirmed, trigger suppression)
        """
        fire_flag = False
        smoke_flag = False
        highest_fire_conf = 0.0
        
        for det in detections:
            cls_name = det['class'].lower()
            conf = det['confidence']
            
            if 'fire' in cls_name and conf > self.fire_conf_threshold:
                fire_flag = True
                highest_fire_conf = max(highest_fire_conf, conf)
            
            if 'smoke' in cls_name and conf > self.fire_conf_threshold:
                smoke_flag = True

        sensor_flag = False
        if (temperature is not None and temperature > self.temp_threshold) or \
           (gas_value is not None and gas_value > self.gas_threshold):
            sensor_flag = True

        # Rule engine
        result = 0
        
        # Scenario 1: High confidence fire + high gas = Immediate Suppression
        if highest_fire_conf > self.high_fire_conf and (gas_value is not None and gas_value > self.gas_threshold * 1.5):
            logging.critical("CRITICAL: HIGH CONFIDENCE FIRE + EXTREME GAS DETECTED.")
            result = 2
            
        # Scenario 2: Fire confirmed by visual AND sensors = Trigger Suppression
        elif fire_flag and sensor_flag:
            logging.critical("CRITICAL: MULTI-MODAL FIRE DETECTED (Visual + Sensors).")
            result = 2
            
        # Scenario 3: Fire detected visually, sensors normal = Alert
        elif fire_flag and not sensor_flag:
            logging.warning("WARNING: Visual fire detected, sensors normal.")
            result = 1
            
        # Scenario 4: Sensors high, no visual fire = Alert
        elif not fire_flag and sensor_flag:
            logging.warning("WARNING: Sensor thresholds exceeded, no visual fire detected.")
            result = 1
            
        elif smoke_flag:
            logging.warning("WARNING: Visual smoke detected.")
            result = 1

        return result
