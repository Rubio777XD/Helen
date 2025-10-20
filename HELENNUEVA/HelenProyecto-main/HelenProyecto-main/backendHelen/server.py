import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request, jsonify, Response, render_template
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__)
app.config['debug'] = True
app.config['SECRET_KEY'] = 'mysecret'

CORS(app, resources={r"/api/*": {"origins": "*"}})

socket = SocketIO()
socket.init_app(app, cors_allowed_origins="*")

OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '6266f75957014a7de4ae0ded34d1e7cc')
DEFAULT_COORDS = {
    'lat': float(os.getenv('DEFAULT_LAT', 32.43347)),
    'lon': float(os.getenv('DEFAULT_LON', -116.67447)),
}


def _call_openweather(endpoint: str, params: dict | None = None):
    if not OPENWEATHER_API_KEY:
        return None, (jsonify({'error': 'OpenWeather API key not configured'}), 500)

    params = params.copy() if params else {}
    params.setdefault('appid', OPENWEATHER_API_KEY)
    try:
        response = requests.get(f'https://api.openweathermap.org{endpoint}', params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        return None, (jsonify({'error': 'Failed to contact OpenWeather', 'details': str(exc)}), 502)
    return response.json(), None


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/api/weather/current')
def api_weather_current():
    lat = request.args.get('lat', type=float, default=DEFAULT_COORDS['lat'])
    lon = request.args.get('lon', type=float, default=DEFAULT_COORDS['lon'])
    units = request.args.get('units', default='metric')
    lang = request.args.get('lang', default='es')

    data, error = _call_openweather('/data/2.5/weather', {
        'lat': lat,
        'lon': lon,
        'units': units,
        'lang': lang,
    })
    if error:
        return error
    return jsonify(data)


@app.get('/api/weather/forecast')
def api_weather_forecast():
    lat = request.args.get('lat', type=float, default=DEFAULT_COORDS['lat'])
    lon = request.args.get('lon', type=float, default=DEFAULT_COORDS['lon'])
    units = request.args.get('units', default='metric')
    lang = request.args.get('lang', default='es')

    data, error = _call_openweather('/data/2.5/forecast', {
        'lat': lat,
        'lon': lon,
        'units': units,
        'lang': lang,
    })
    if error:
        return error
    return jsonify(data)


@app.get('/api/weather/reverse-geocoding')
def api_weather_reverse_geocoding():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    if lat is None or lon is None:
        return jsonify({'error': 'lat and lon are required'}), 400

    data, error = _call_openweather('/geo/1.0/reverse', {
        'lat': lat,
        'lon': lon,
        'limit': request.args.get('limit', default=1, type=int) or 1,
    })
    if error:
        return error
    return jsonify(data)


@app.get('/api/time')
def api_time():
    timezone_name = request.args.get('timezone', 'UTC')
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        return jsonify({'error': 'invalid timezone'}), 400

    now = datetime.now(tz)
    payload = {
        'timezone': timezone_name,
        'iso': now.isoformat(),
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H:%M:%S'),
        'timestamp': now.timestamp(),
    }
    return jsonify(payload)


@app.route('/health', methods=['GET'])
def health():
    data = {'status': 'ok'}
    socket.emit('message', data)
    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/gestures/gesture-key', methods=['POST'])
def publish_gesture_key():
    """
    Request data format:
    {
        "key": "char",
        "gesture": "gesture_name",
    }
    """
    data = request.json
    print(data)
    try:
        socket.emit('message', data)
    except Exception:
        return Response(status=500)
    return Response(status=200)


@socket.on('connect')
def connect():
    print('client connected')


@socket.on('message')
def message(data):
    print(f'message: {data}')


if __name__ == '__main__':
    socket.run(app, host='127.0.0.1', port=5000, debug=True)
