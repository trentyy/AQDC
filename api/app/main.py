import json
import os
from datetime import datetime
from flask import Flask, request, jsonify
from sqlalchemy import create_engine
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
load_dotenv()

HOST = os.getenv("DBHOST")
USER = os.getenv("USER")
PW = os.getenv("PW")
DB = os.getenv("DB")

app = Flask(__name__)
print(f'mysql+pymysql://{USER}:{PW}@{HOST}/{DB}')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{USER}:{PW}@{HOST}/{DB}'

db = SQLAlchemy(app)

class AM2108_Data(db.Model):
    __tablename__ = "fridge_AM2108"
    time = db.Column(db.DateTime, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def hello_world():
    return 'testing page'
@app.route('/addData/fridge/AM2108', methods=['POST'])
def add_sensor_data():
    if request.is_json:
        data = request.get_json()
        current_time = datetime.now()
        temperature = data.get('fridge_AM2108').get('Temperature')
        humidity = data.get('fridge_AM2108').get('Humidity')
        print(temperature, humidity)

        am2108_data = AM2108_Data(time=current_time,
                                  temperature=temperature,
                                  humidity=humidity)
        db.session.add(am2108_data)
        db.session.commit()
        return jsonify({"message": "Data added successfully"}), 200
    else:
        return jsonify({"error": "Invalid request format, expected JSON"}), 400
    
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8888,debug=True)