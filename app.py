import dash
from dash import dcc, html, Output, Input
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import pandas as pd
from datetime import datetime, timedelta, time
import xmlrpc.client
import pytz
import os
import dash_auth  # New import for authentication

# === CONFIGURATION ===
app = dash.Dash(__name__)
server = app.server  # Required for deployment with Gunicorn

# Add Basic Auth (credentials from env vars)
AUTH_PAIRS = {
    os.environ.get('DASH_USERNAME', 'default_user'): os.environ.get('DASH_PASSWORD', 'default_pass')
}
dash_auth.BasicAuth(app, AUTH_PAIRS)

ODOO_URL = os.environ['ODOO_URL']
ODOO_DB = os.environ['ODOO_DB']
ODOO_USERNAME = os.environ['ODOO_USERNAME']
ODOO_PASSWORD = os.environ['ODOO_PASSWORD']
MODEL_NAME = 'x_counter_scale'
TZ = pytz.timezone('Europe/Paris')

pio.renderers.default = 'browser'

# === FETCH DATA FROM ODOO ===
def fetch_data():
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    if not uid:
        raise ValueError("Authentication failed")
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    now_utc = datetime.now(pytz.utc)
    start_time = now_utc - timedelta(days=10)  # Increased to 10 days to ensure all data is fetched
    start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
    domain = [('x_time_stamp_counter_scale_01', '>=', start_str)]
    fields = ['x_time_stamp_counter_scale_01', 'x_mass_counter_scale_01']
    records = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, MODEL_NAME, 'search_read', [domain], {'fields': fields, 'order': 'x_time_stamp_counter_scale_01 ASC'})
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame()
    df['time_stamp'] = pd.to_datetime(df['x_time_stamp_counter_scale_01']).dt.tz_localize('UTC').dt.tz_convert(TZ)
    df['mass'] = df['x_mass_counter_scale_01'].astype(float)
    return df[['time_stamp', 'mass']]

# === LOAD DATA ===
def load_data():
    df = fetch_data()
    now = datetime.now(TZ)
    if df.empty:
        current_tph = 0
        current_cumulative = 0
        summary_df = pd.DataFrame()
        df_24h = pd.DataFrame()
        return current_tph, current_cumulative, summary_df, df_24h

    # === Compute get_gauge_values ===
    cur_time = now.time()
    cur_date = now.date()
    if time(6, 0) <= cur_time < time(14, 0):
        shift_start = datetime.combine(cur_date, time(6, 0), tzinfo=now.tzinfo)
    elif time(14, 0) <= cur_time < time(22, 0):
        shift_start = datetime.combine(cur_date, time(14, 0), tzinfo=now.tzinfo)
    else:
        shift_date = cur_date if cur_time >= time(22, 0) else cur_date - timedelta(days=1)
        shift_start = datetime.combine(shift_date, time(22, 0), tzinfo=now.tzinfo)
    shift_end = shift_start + timedelta(hours=8)
    shift_df = df[(df['time_stamp'] >= shift_start) & (df['time_stamp'] < shift_end)]
    shift_sum_tonnes = shift_df['mass'].sum() * 2
    current_cumulative = float(shift_sum_tonnes)
    # Last 5 minutes
    last_5min_start = now - timedelta(minutes=5)
    last_df = df[df['time_stamp'] >= last_5min_start]
    if last_df.empty:
        current_tph = 0
    else:
        min_time = last_df['time_stamp'].min()
        max_time = last_df['time_stamp'].max()
        total_mass = last_df['mass'].sum()
        delta_min = (max_time - min_time).total_seconds() / 60 if max_time > min_time else 0
        current_tph = round((total_mass / delta_min) * 60 * 2, 2) if delta_min > 0 else 0
    current_tph = float(current_tph)

    # === Compute shift_summary_view ===
    today = now.date()
    yesterday = today - timedelta(days=1)
    twodaysago = today - timedelta(days=2)
    threedaysago = today - timedelta(days=3)
    all_shifts = [
        {'shift': 'Morning', 'start': datetime.combine(today, time(6,0), tzinfo=now.tzinfo), 'end': datetime.combine(today, time(14,0), tzinfo=now.tzinfo)},
        {'shift': 'Afternoon', 'start': datetime.combine(today, time(14,0), tzinfo=now.tzinfo), 'end': datetime.combine(today, time(22,0), tzinfo=now.tzinfo)},
        {'shift': 'Night', 'start': datetime.combine(yesterday, time(22,0), tzinfo=now.tzinfo), 'end': datetime.combine(today, time(6,0), tzinfo=now.tzinfo)},
        {'shift': 'Morning', 'start': datetime.combine(yesterday, time(6,0), tzinfo=now.tzinfo), 'end': datetime.combine(yesterday, time(14,0), tzinfo=now.tzinfo)},
        {'shift': 'Afternoon', 'start': datetime.combine(yesterday, time(14,0), tzinfo=now.tzinfo), 'end': datetime.combine(yesterday, time(22,0), tzinfo=now.tzinfo)},
        {'shift': 'Night', 'start': datetime.combine(twodaysago, time(22,0), tzinfo=now.tzinfo), 'end': datetime.combine(yesterday, time(6,0), tzinfo=now.tzinfo)},
        {'shift': 'Morning', 'start': datetime.combine(twodaysago, time(6,0), tzinfo=now.tzinfo), 'end': datetime.combine(twodaysago, time(14,0), tzinfo=now.tzinfo)},
        {'shift': 'Afternoon', 'start': datetime.combine(twodaysago, time(14,0), tzinfo=now.tzinfo), 'end': datetime.combine(twodaysago, time(22,0), tzinfo=now.tzinfo)},
        {'shift': 'Night', 'start': datetime.combine(threedaysago, time(22,0), tzinfo=now.tzinfo), 'end': datetime.combine(twodaysago, time(6,0), tzinfo=now.tzinfo)},
    ]
    recent_shifts = [s for s in all_shifts if s['end'] <= now]
    recent_shifts = sorted(recent_shifts, key=lambda x: x['end'], reverse=True)[:6]
    summary_data = []
    for rs in recent_shifts:
        shift_df = df[(df['time_stamp'] >= rs['start']) & (df['time_stamp'] < rs['end'])]
        shift_tph = round(shift_df['mass'].sum() * 2, 1)
        shift_df_copy = shift_df.copy()
        shift_df_copy['interval_id'] = shift_df_copy['time_stamp'].apply(lambda x: int(x.timestamp()) // 300)
        active_df = shift_df_copy[shift_df_copy['mass'] > 0.05]
        if not active_df.empty:
            active_intervals = active_df['interval_id'].nunique()
            intervals_mass = active_df.groupby('interval_id')['mass'].sum()
            avg_running_tph = round((intervals_mass.sum() * 2) / (active_intervals * 5 / 60), 2) if active_intervals > 0 else 0
        else:
            active_intervals = 0
            avg_running_tph = 0
        hours_on = round(active_intervals * 5.0 / 60, 2)
        up_percent = round((active_intervals * 5.0 / 60 / 8) * 100, 2)
        util_percent = round((shift_df['mass'].sum() * 2 / 400) * 100, 2)
        summary_data.append({
            'Date': rs['start'].date(),
            'Shift': rs['shift'],
            'Shift_TPH': shift_tph,
            'Hours_ON': hours_on,
            'AVG_Running_TPH': avg_running_tph,
            'UP_Percent': up_percent,
            'Util_Percent': util_percent
        })
    summary_df = pd.DataFrame(summary_data)

    # === Compute get_24h_summary ===
    recent_24h_shifts = [s for s in all_shifts if s['end'] <= now]
    recent_24h_shifts = sorted(recent_24h_shifts, key=lambda x: x['end'], reverse=True)[:3]
    df_24 = df[df['time_stamp'].apply(lambda x: any(rs['start'] <= x < rs['end'] for rs in recent_24h_shifts))]
    df_24_copy = df_24.copy()
    df_24_copy['interval_id'] = df_24_copy['time_stamp'].apply(lambda x: int(x.timestamp()) // 300)
    intervals_24 = df_24_copy.groupby('interval_id')['mass'].sum().reset_index(name='interval_mass')
    total_mass = intervals_24['interval_mass'].sum()
    total_tons = total_mass * 2
    active_intervals = intervals_24[intervals_24['interval_mass'] > 0.05].shape[0]
    total_daily_tph = round(total_tons, 2)
    total_daily_hours = round(active_intervals * 5 / 60.0, 2)
    avg_daily_tph = round(total_tons / total_daily_hours, 2) if total_daily_hours > 0 else 0
    up_percent = round((active_intervals * 5 / 1440.0) * 100, 2)
    util_percent = round((total_tons / 1200) * 100, 2)
    df_24h = pd.DataFrame([{
        'Total Daily TPH': total_daily_tph,
        'Total Daily Hours': total_daily_hours,
        'AVG Daily TPH': avg_daily_tph,
        'UP_Percent': up_percent,
        'Util_Percent': util_percent
    }])

    # Rename columns for summary_df
    column_renames = {
        "Shift_TPH": "Shift TPH",
        "Hours_ON": "Hours ON",
        "AVG_Running_TPH": "TPH Average",
        "UP_Percent": "Percent ON",
        "Util_Percent": "Utilization Percent"
    }
    summary_df.rename(columns=column_renames, inplace=True)

    return current_tph, current_cumulative, summary_df, df_24h

# === BUILD DASHBOARD ===
def build_dashboard(current_tph, current_cumulative, summary_df, df_24h):
    rows = 2 if not summary_df.empty and not df_24h.empty else 1
    fig = make_subplots(
        rows=rows, cols=2,
        specs=[[{"type": "indicator"}, {"type": "indicator"}]] + ([ [{"type": "table"}, {"type": "table"}] ] if rows == 2 else []),
        column_widths=[0.5, 0.5],
        subplot_titles=("Current TPH", "Cumulative Last Shift") + (("Latest Shifts Summary", "24H Summary") if rows == 2 else ())
    )

    # === GAUGE: Current TPH ===
    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=current_tph,
        delta={'reference': 50, 'increasing': {'color': "#FF0000"}},
        gauge={
            'axis': {'range': [0, 60]},
            'bar': {'color': "darkgreen"},
            'steps': [
                {'range': [0, 15], 'color': "#FF0000"},
                {'range': [15, 30], 'color': "#FFA500"},
                {'range': [30, 45], 'color': "#FFFF00"},
                {'range': [45, 60], 'color': "#008000"}
            ]
        }
    ), row=1, col=1)

    # === GAUGE: Cumulative ===
    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=current_cumulative,
        delta={'reference': 400, 'increasing': {'color': "#FF0000"}},
        gauge={
            'axis': {'range': [0, 480]},
            'bar': {'color': "blue"},
            'steps': [
                {'range': [0, 120], 'color': "#FF0000"},
                {'range': [120, 240], 'color': "#FFA500"},
                {'range': [240, 360], 'color': "#FFFF00"},
                {'range': [360, 480], 'color': "#008000"}
            ]
        }
    ), row=1, col=2)

    # === TABLE: Last 3 Shifts ===
    if not summary_df.empty:
        fig.add_trace(go.Table(
            header=dict(
                values=list(summary_df.columns),
                fill_color='black',
                font=dict(color='white', size=16),
                align='left',
                height=32
            ),
            cells=dict(
                values=[summary_df[col] for col in summary_df.columns],
                fill_color='white',
                font=dict(color='black', size=14),
                align='left',
                height=30
            )
        ), row=2, col=1)

    # === TABLE: 24H Summary ===
    if not df_24h.empty:
        fig.add_trace(go.Table(
            header=dict(
                values=list(df_24h.columns),
                fill_color='black',
                font=dict(color='white', size=16),
                align='left',
                height=32
            ),
            cells=dict(
                values=[df_24h[col] for col in df_24h.columns],
                fill_color='white',
                font=dict(color='black', size=14),
                align='left',
                height=30
            )
        ), row=2, col=2)

    # === LAYOUT ===
    fig.update_layout(
        autosize=True,
        height=850,
        margin=dict(t=110, b=40, l=50, r=50),
        paper_bgcolor="white",
        font=dict(size=18),
        grid=dict(
            rows=rows,
            columns=2,
            pattern="independent",
            domain=dict(x=[0, 1], y=[0, 1])
        )
    )

    # === POSITION TITLES ===
    fig.layout.annotations[0].update(y=1.12, font_size=20)
    fig.layout.annotations[1].update(y=1.12, font_size=20)
    if rows == 2:
        fig.layout.annotations[2].update(y=0.45, x=0.25, font_size=18)
        fig.layout.annotations[3].update(y=0.45, x=0.75, font_size=18)

    return fig

# === LAYOUT ===
app.layout = html.Div([
    html.Button("Refresh", id="refresh-button", style={"margin": "20px", "fontSize": "16px", "padding": "10px 20px", "display": "inline-block"}),
    html.P(id="last-update", style={"margin": "0 0 0 10px", "fontSize": "12px", "fontFamily": "Arial", "display": "inline-block"}),
    dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0),
    dcc.Graph(id="dashboard-graph", style={"margin": "0 auto", "width": "100%", "height": "100vh"})
])

# === CALLBACK ===
@app.callback(
    [Output("dashboard-graph", "figure"),
     Output("last-update", "children")],
    [Input("refresh-button", "n_clicks"), Input('interval-component', 'n_intervals')]
)
def update_dashboard(n_clicks, n_intervals):
    if n_clicks is None and n_intervals == 0:
        n_clicks = 0
    current_tph, current_cumulative, summary_df, df_24h = load_data()
    fig = build_dashboard(current_tph, current_cumulative, summary_df, df_24h)
    last_update_time = datetime.now(TZ)
    last_update = f"Last updated: {last_update_time.strftime('%Y-%m-%d %H:%M:%S')}"
    return fig, last_update

# === RUN ===
if __name__ == "__main__":
    app.run(debug=True, port=8050)