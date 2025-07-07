from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import os
from io import BytesIO
from datetime import timedelta
from werkzeug.security import check_password_hash
from pymongo import MongoClient
import urllib.parse

matplotlib.use('Agg')

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.permanent_session_lifetime = timedelta(minutes=5)

# --- MongoDB Connection ---
username = urllib.parse.quote_plus("narasimhayalakarajula")
password = urllib.parse.quote_plus("@Nss1125sl1977")

client = MongoClient(f"mongodb+srv://{username}:{password}@cluster0.rwfdfzy.mongodb.net/?retryWrites=true&w=majority")

# Admin User DB
user_db = client["user"]
user_collection = user_db["user"]

# States Data DB
mongo_db = client["states"]
states_collection = mongo_db["states"]

# CSV Path & Chart Directory
CSV_PATH = 'India_Agriculture.csv'
CHARTS_DIR = 'static/charts'
os.makedirs(CHARTS_DIR, exist_ok=True)

# ---------------- ROUTES ----------------

@app.route('/')
def home():
    return render_template('HomePage.html')

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = user_collection.find_one({'username': username})

        if user:
            hashed_pw = user.get('password')
            if hashed_pw and check_password_hash(hashed_pw, password):
                session['admin'] = username
                flash("Login successful!", "success")
                return redirect(url_for('data_entry'))
            else:
                flash("Incorrect password.", "danger")
        else:
            flash("User not found.", "danger")

    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('admin_login'))

@app.route('/admin/data-entry', methods=['GET', 'POST'])
def data_entry():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    df = pd.read_csv(CSV_PATH)
    df.columns = df.columns.str.strip()
    df.dropna(subset=['State', 'District', 'Crop', 'Season'], inplace=True)

    columns = df.columns.tolist()
    states = sorted(df['State'].unique())
    crops = sorted(df['Crop'].unique())
    seasons = sorted(df['Season'].unique())
    districts_by_state = df.groupby('State')['District'].unique().apply(list).to_dict()

    if request.method == 'POST':
        new_row = {col: request.form.get(col, '').strip() for col in columns}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(CSV_PATH, index=False)
        flash("Data successfully added.", "success")
        return redirect(url_for('data_entry'))

    return render_template(
        'data_entry.html',
        columns=columns,
        states=states,
        crops=crops,
        seasons=seasons,
        districts_by_state=districts_by_state
    )

@app.route('/visualization', methods=['GET', 'POST'])
def visualization():
    df = pd.read_csv(CSV_PATH, low_memory=False)
    df.columns = df.columns.str.strip()
    df['Area'] = pd.to_numeric(df['Area'], errors='coerce')
    df['Production'] = pd.to_numeric(df['Production'], errors='coerce')
    df.dropna(subset=['State', 'Crop_Year', 'Season', 'Production'], inplace=True)

    states = sorted(df['State'].unique())
    seasons = sorted(df['Season'].unique())
    years = sorted(df['Crop_Year'].unique())

    selected_state = request.form.get('state') or states[0]
    selected_season = request.form.get('season') or seasons[0]
    selected_year = int(request.form.get('year') or years[0])

    filtered = df[
        (df['State'] == selected_state) &
        (df['Season'] == selected_season) &
        (df['Crop_Year'] == selected_year)
    ]

    chart_paths = []
    for f in os.listdir(CHARTS_DIR):
        os.remove(os.path.join(CHARTS_DIR, f))

    if not filtered.empty:
        crop_production = filtered.groupby('Crop')['Production'].sum().sort_values(ascending=True)

        if len(crop_production) > 1:
            crops = crop_production.index.tolist()
            values = crop_production.values.tolist()
            cmap = plt.cm.get_cmap('Set3', len(crops))
            colors = [cmap(i) for i in range(len(crops))]

            plt.figure(figsize=(28, 14))
            bars = plt.barh(crops, values, color=colors, edgecolor='black')
            plt.xlabel("Total Production (tonnes)", fontsize=18)
            plt.ylabel("Crops", fontsize=18)
            plt.title(f"Crop Production in {selected_state} ({selected_season}, {selected_year})", fontsize=22)

            for bar in bars:
                width = bar.get_width()
                plt.text(width + max(values)*0.01, bar.get_y() + bar.get_height()/2, f"{int(width):,}", va='center', fontsize=14)

            from matplotlib.patches import Patch
            legend_elements = [Patch(facecolor=colors[i], edgecolor='black', label=crops[i]) for i in range(len(crops))]
            plt.legend(handles=legend_elements, title='Crops', loc='center left', bbox_to_anchor=(1, 0.5), fontsize=12)

            plt.tight_layout()
            path = f'{CHARTS_DIR}/crop_bar_{selected_state}_{selected_year}.png'
            plt.savefig(path, bbox_inches='tight', dpi=200)
            chart_paths.append(path.replace('static/', ''))
            plt.close()

    return render_template(
        'visualization.html',
        chart_paths=chart_paths,
        states=states,
        seasons=seasons,
        years=years,
        selected_state=selected_state,
        selected_season=selected_season,
        selected_year=selected_year
    )

@app.route('/state/<state_name>')
def state_page(state_name):
    return render_template(f'states/{state_name}.html', state_name=state_name)

@app.route('/chart/<path:state_name>.png')
def state_chart(state_name):
    df = pd.read_csv(CSV_PATH, low_memory=False)
    df.columns = df.columns.str.strip()

    df['Production'] = pd.to_numeric(df['Production'], errors='coerce')
    df['Crop_Year'] = pd.to_numeric(df['Crop_Year'], errors='coerce')

    clean_name = state_name.replace('-', ' ').strip().title()

    filtered = df[
        (df['State'].str.strip().str.lower() == clean_name.lower()) &
        (df['Crop_Year'] >= 2010) &
        (df['Crop_Year'] <= 2019)
    ]

    if filtered.empty:
        return '', 404

    yearly_production = (
        filtered.groupby('Crop_Year')['Production']
        .sum()
        .sort_index()
    )

    plt.figure(figsize=(15, 8))
    plt.bar(yearly_production.index.astype(str), yearly_production.values, color='seagreen')
    plt.title(f'Total Crop Production in {clean_name} (2010–2019)', fontsize=16)
    plt.xlabel('Year')
    plt.ylabel('Total Production (Tonnes)')
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    img.seek(0)
    return send_file(img, mimetype='image/png')

@app.route('/ai-prediction', methods=['GET', 'POST'])
def airecomm():
    return render_template('airecomm.html')

@app.route('/schemes')
def schemes():
    return render_template('schemes.html')

@app.route('/dataanalytics')
def dataanalytics():
    return render_template('dataanalytics.html')

@app.route('/crop/<crop>')
def crop_info(crop):
    allowed_crops = ['rice', 'wheat', 'cotton', 'jute', 'millet', 'tea', 'sugarcane']
    crop = crop.lower()
    if crop in allowed_crops:
        return render_template(f'crops/{crop}.html')
    else:
        return "Crop not found", 404

from bson import ObjectId

@app.route('/states/<state_slug>')
def dynamic_state_page(state_slug):
    state_data = states_collection.find_one({"slug": state_slug})
    if state_data:
        state_data['_id'] = str(state_data['_id'])
        return render_template("state_dynamic.html", state=state_data)
    else:
        abort(404)
@app.route('/heatmap')
def heatmap():
    df = pd.read_csv('India_Agriculture.csv')
    df['Area'] = pd.to_numeric(df['Area'], errors='coerce')
    df['Production'] = pd.to_numeric(df['Production'], errors='coerce')

    # Yield per hectare
    state_yield = df.groupby('State').apply(lambda x: x['Production'].sum() / x['Area'].sum()).to_dict()

    return render_template('heatmap.html', state_yield=state_yield)
if __name__ == '__main__':
    print("✅ Flask running at http://127.0.0.1:5050")
    app.run(debug=True, port=5050)