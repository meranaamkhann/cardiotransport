# CardioTransport
Flask + scikit-learn web app implementing the paper *Cross-Cohort CAD Prediction Using Interpretable and Calibration-Aware ML*.
```
pip install -r requirements.txt
python train.py     # downloads UCI data, trains, writes model/ and static/data/metrics.json
python app.py       # http://localhost:5000
```
Deploy: Dockerfile is ready for Hugging Face Spaces (Docker SDK, port 7860). Research prototype, not a medical device.
