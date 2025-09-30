from fastapi import FastAPI
from pydantic import BaseModel, Field
from google.cloud import storage
from prophet.serialize import model_from_json
import json
import logging
import time
import sys

# Load the model (from the local source)
# with open('temp_forecaster.json', 'r') as fin:
#     m = model_from_json(fin.read())  # Load model

# Load the model form a cloud service

BUCKET_NAME = "gemini1-ml-api-models-bucket" # IMPORTANT: Use your actual bucket name!
MODEL_FILE_NAME = "temp_forecaster.json"
LOCAL_MODEL_PATH = "/tmp/temp_forecaster.json" 
MODEL = None

# Get the logger instance
prediction_logger = logging.getLogger('prediction_log')
prediction_logger.setLevel(logging.INFO)

app = FastAPI(
    title="Prophet Forecaster of Mean Temperature (Daily) New Delhi",
    version = "0.0.1",
    description="Trained on temperature data for new dalily. Returns the temperature for the next n days according to the user request"
)

@app.on_event("startup") # running the code once at launch
def startup_event():
    setup_logging()
    load_model_from_gcs()

def setup_logging():
    # Only configure if no handler is present
    if not prediction_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        prediction_logger.addHandler(handler)
        prediction_logger.setLevel(logging.INFO)
        
def load_model_from_gcs():
    try: 
        print(f"Loading model from GCS bucket: {BUCKET_NAME}")
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(MODEL_FILE_NAME)
        blob.download_to_filename(LOCAL_MODEL_PATH)
        # Load the model from the local temporary file
        global MODEL
        with open(LOCAL_MODEL_PATH, 'r', encoding='utf-8') as file:
            MODEL = model_from_json(file.read())
        print("Model loaded successfully from GCS")
    except Exception as e:
        print(f"Error loading model from GCS: {e}")
        global MODEL
        MODEL = None

class InputDays(BaseModel):
    n_days: int = Field(ge=1)


@app.get("/")
def read_root():
    return {"Hello" : "This is my temperature app v1.1"} 


@app.post("/next_days_temp")
def get_predictions(item: InputDays):
    if MODEL:
        start_time = time.time()
        future_df = MODEL.make_future_dataframe(periods=item.n_days)
        forecast = MODEL.predict(future_df)
        forecast = forecast[["ds", "yhat"]] # to get the last n_days of predicts
        prediction = forecast.iloc[-item.n_days:,].to_dict()
        end_time = time.time()
        latency_ms = round((end_time - start_time) * 1000, 2) # in milliseconds


        log_data = {
            "event_type": "prediction_request",
            "model_version": "v1.0",
            "input_features": item.n_days,
            "latency_ms": latency_ms,
            "prediction_datetime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "predictions": prediction
        }
        prediction_logger.info(json.dumps(log_data))

        return {"predictions" : prediction}
    else:
        return {"error": "Model is not loaded"}

