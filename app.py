import json
import os
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DATA_FILE = 'server_data.json'


QWEATHER_API_KEY = "93e32b5396dd4359a174d65c059ccbe8" # 例如: "abc123456789def"


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"city": "未知", "weather": {}}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/location', methods=['POST'])
def update_location():
    """1. 将定位城市保存在服务器端"""
    data = request.json
    city = data.get('city', '北京市')
    
    server_state = load_data()
    server_state['city'] = city
    save_data(server_state)
    
    return jsonify({"status": "success", "city": city})

@app.route('/api/weather', methods=['GET'])
def get_weather():
    """3. 天气详情和空气质量指数：在服务器端获取后，传给客户端，并保存在服务器端"""
    city = request.args.get('city')
    if not city:
        server_state = load_data()
        city = server_state.get('city', '北京市')

    # 处理城市名称（去除"市"字以适配各类API规范）
    query_city = city.replace("市", "").replace("省", "")

    try:
        # ================= 需求 2. 真实接口接入方案 =================
        # 根据需求：天气详情和空气质量指数数据可通过“和风天气”获取
        if QWEATHER_API_KEY != "在这里填入您的和风天气API_KEY":
            # 1. 城市查找 (Geo API) - 获取 Location ID
            geo_url = f"https://geoapi.qweather.com/v2/city/lookup?location={query_city}&key={QWEATHER_API_KEY}"
            geo_res = requests.get(geo_url).json()
            location_id = geo_res['location'][0]['id']

            # 2. 和风天气(QWeather) - 获取实时天气详情
            weather_url = f"https://devapi.qweather.com/v7/weather/now?location={location_id}&key={QWEATHER_API_KEY}"
            weather_res = requests.get(weather_url).json()['now']

            # 3. 和风天气(QWeather) - 获取空气质量指数 (AQI)
            aqi_url = f"https://devapi.qweather.com/v7/air/now?location={location_id}&key={QWEATHER_API_KEY}"
            aqi_res = requests.get(aqi_url).json()['now']
            
            # 4. 和风天气(QWeather) - 湿度与温度未来走势 (用于 ECharts 折线图)
            hourly_url = f"https://devapi.qweather.com/v7/weather/24h?location={location_id}&key={QWEATHER_API_KEY}"
            hourly_res = requests.get(hourly_url).json()['hourly']

            forecast_data = []
            for hour in hourly_res[:5]: # 取未来 5 个时间点
                time_str = hour['fxTime'].split('T')[1][:5]
                forecast_data.append({"time": time_str, "temp": int(hour['temp']), "humidity": int(hour['humidity'])})

            weather_data = {
                "city": city,
                "temperature": weather_res['temp'],
                "condition": weather_res['text'],
                "humidity": weather_res['humidity'],
                "aqi": int(aqi_res['aqi']),
                "forecast": forecast_data
            }
        else:
            # == 免费开放免KEY备用方案：wttr.in 真实天气 + aqicn 演示接口 ==
            # 使用真实网络请求获取世界天气服务 (wttr.in)
            wttr_url = f"https://wttr.in/{query_city}?format=j1"
            wttr_res = requests.get(wttr_url, timeout=5).json()
            current_cond = wttr_res['current_condition'][0]
            
            # AQICN 开放测试接口 (部分城市可能返回固定演示数据)
            aqi_demo_url = f"https://api.waqi.info/feed/{query_city}/?token=demo"
            aqi_res = requests.get(aqi_demo_url, timeout=5).json()
            real_aqi = aqi_res.get('data', {}).get('aqi', 75) if aqi_res.get('status') == 'ok' else 75

            hourly = wttr_res['weather'][0]['hourly']
            forecast_data = []
            for h in hourly[:5]:
                time_str = f"{int(h['time'])//100:02d}:00" if h['time'] != '0' else '00:00'
                forecast_data.append({
                    "time": time_str,
                    "temp": int(h['tempC']),
                    "humidity": int(h['humidity'])
                })

            # 解析实时情况（如果 wttr.in 的全英数据不易读，做简单映射）
            cond_en = current_cond['weatherDesc'][0]['value'].lower()
            cond_zh = "晴" if "clear" in cond_en or "sun" in cond_en else "多云" if "cloud" in cond_en else "雨" if "rain" in cond_en else "阴"

            weather_data = {
                "city": city,
                "temperature": current_cond['temp_C'],
                "condition": cond_zh,
                "humidity": current_cond['humidity'],
                "aqi": int(real_aqi),
                "forecast": forecast_data
            }
            
    except Exception as e:
        print(f"获取真实天气失败: {e}")
        # 异常兜底保护机制
        weather_data = {
            "city": city,
            "aqi": 88,
            "temperature": 22,
            "humidity": 45,
            "condition": "网络异常-默认",
            "forecast": [{"time": "12:00", "temp": 22, "humidity": 45}]
        }
    
    # 将真实天气数据保存在服务器端
    server_state = load_data()
    server_state['weather'] = weather_data
    save_data(server_state)
    
    return jsonify(weather_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    host = os.environ.get('HOST', '0.0.0.0')
    print("=" * 65)
    print("服务器已启动，建议将项目部署到云主机或 PaaS 平台后使用浏览器直接访问。")
   
    print("如果在本机调试，可访问本机地址：")
    print(f"http://127.0.0.1:{port} 或 http://{host}:{port}")
    print("=" * 65)
    app.run(debug=True, port=port, host=host, use_reloader=False)
