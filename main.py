from fastapi import FastAPI
from pydantic import BaseModel, Field
from google.cloud import storage
from prophet.serialize import model_from_json
import json


# Load the model (from the local source)
# with open('temp_forecaster.json', 'r') as fin:
#     m = model_from_json(fin.read())  # Load model

# Load the model form a cloud service

BUCKET_NAME = "gemini1-ml-api-models-bucket" # IMPORTANT: Use your actual bucket name!
MODEL_FILE_NAME = "temp_forecaster.json"
LOCAL_MODEL_PATH = "/tmp/temp_forecaster.json" 
MODEL = None

app = FastAPI(
    title="Prophet Forecaster of Mean Temperature (Daily) New Delhi",
    version = "0.0.1",
    description="Trained on temperature data for new dalily. Returns the temperature for the next n days according to the user request"
)

@app.on_event("startup") # running the code once at luch
def load_model_from_gcs():
    try: 
        print(f"Loading model from GCS bucket: {BUCKET_NAME}")
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(MODEL_FILE_NAME)
        blob.download_to_filename(LOCAL_MODEL_PATH)
        # Load the model from the local temporary file
        global MODEL
        with open(LOCAL_MODEL_PATH, 'r') as file:
            MODEL = model_from_json(file.read())
        print("Model loaded successfully from GCS")
    except Exception as e:
        print(f"Error loading model from GCS: {e}")
        MODEL = None

class InputDays(BaseModel):
    n_days: int = Field(ge=1)


@app.get("/")
def read_root():
    return {"Hello" : "This is my temperature app"} 


@app.post("/next_days_temp")
def get_predictions(item: InputDays):
    if MODEL:
        future_df = MODEL.make_future_dataframe(periods=item.n_days)
        forecast = MODEL.predict(future_df)
        forecast = forecast[["ds", "yhat"]] # to get the last n_days of predicts
        return {"predictions" : forecast.iloc[-item.n_days:,].to_dict()}
    else:
        return {"error": "Model is not loaded"}
