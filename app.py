import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import time
import plotly.graph_objects as go
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import flask
from flask_caching import Cache

INPUT_URL = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/"
df_lookup = pd.read_csv(INPUT_URL+"UID_ISO_FIPS_LookUp_Table.csv");

def transform_and_standardize(df, var_name):
    df = df.drop(columns=['Lat', 'Long']).merge(
        df_lookup.rename(columns={'Country_Region': 'Country/Region', 'Province_State': 'Province/State'})[['Country/Region', 'Province/State', 'iso3','Population']],
        how='outer',
        on=['Country/Region', 'Province/State']
    ).dropna(subset=["iso3"])
    df = df.groupby(['iso3','Country/Region']).sum().reset_index()
    df = df.melt(id_vars=[df.columns[0],df.columns[1],df.columns[-1]], 
        value_vars=df.columns[2:-1], 
        var_name='date', 
        value_name=var_name
    ).dropna()
    df['date']=pd.to_datetime(df['date'])
    return df.sort_values(by=['iso3', 'date'])

def transform_and_standardize_us(df, var_name):
    if var_name is 'deaths':
        df=df.drop(columns=['Population'])
    df = df.drop(columns=['UID','iso2','iso3','Country_Region','code3','Lat','Long_']).groupby(['FIPS','Admin2','Province_State']).sum().reset_index()
    df = df.melt(id_vars=[df.columns[0],df.columns[1],df.columns[2]], 
        value_vars=df.columns[3:], 
        var_name='date', 
        value_name=var_name
    ).dropna()
    df['date']=pd.to_datetime(df['date'])
    return df.sort_values(by=['FIPS', 'date'])

df_confirmed = transform_and_standardize(pd.read_csv(INPUT_URL+"csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"), 'confirmed')
df_deaths = transform_and_standardize(pd.read_csv(INPUT_URL+"csse_covid_19_time_series/time_series_covid19_deaths_global.csv"), 'deaths')
df_recovered = transform_and_standardize(pd.read_csv(INPUT_URL+"csse_covid_19_time_series/time_series_covid19_recovered_global.csv"), 'recovered')
df = df_confirmed.merge(df_deaths,how='outer',on=['date', 'iso3', 'Population','Country/Region']).merge(df_recovered,how='outer',on=['date', 'iso3', 'Population','Country/Region'])
df['days']=(df['date'] - df['date'][0]).dt.days
for col in ['confirmed', 'deaths', 'recovered']:
    df[f'{col}_rate'] = (df[col]/df['Population']*100000000).astype('int64')

df_confirmed_us = transform_and_standardize_us(pd.read_csv(INPUT_URL+"csse_covid_19_time_series/time_series_covid19_confirmed_US.csv"), 'confirmed')
df_deaths_us = transform_and_standardize_us(pd.read_csv(INPUT_URL+"csse_covid_19_time_series/time_series_covid19_deaths_US.csv"), 'deaths')
df_us=df_confirmed_us.merge(df_deaths_us,how='outer',on=['date', 'FIPS', 'Admin2','Province_State'])
df_us=df_us.merge(df_lookup[['FIPS','Population']],
                    how='outer',
                    on=['FIPS']).dropna()
df_us = df_us.astype({'FIPS':'int','confirmed':'int','deaths':'int','Population':'int'})
df_us['days']=(df_us['date'] - df_us['date'][0]).dt.days
for col in ['confirmed', 'deaths']:
    df_states[f'{col}_rate'] = (df_states[col]/df_states['Population']*100000000).astype('int64')
df_states['abbreviation']=df_states['Province_State'].map({'Alabama':'AL','Alaska':'AK','American Samoa':'AS','Arizona':'AZ','Arkansas':'AR','California':'CA','Colorado':'CO','Connecticut':'CT','Delaware':'DE','District of Columbia':'DC','Florida':'FL','Georgia':'GA','Guam':'GU','Hawaii':'HI','Idaho':'ID','Illinois':'IL','Indiana':'IN','Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME','Maryland':'MD','Massachusetts':'MA','Michigan':'MI','Minnesota':'MN','Mississippi':'MS','Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV','New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM','New York':'NY','North Carolina':'NC','North Dakota':'ND','Northern Mariana Islands':'MP','Ohio':'OH','Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA','Puerto Rico':'PR','Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD','Tennessee':'TN','Texas':'TX','Utah':'UT','Vermont':'VT','Virgin Islands':'VI','Virginia':'VA','Washington':'WA','West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY'})

unixTimeMillis = lambda dt: int(time.mktime(dt.timetuple()))

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css', 'https://codepen.io/chriddyp/pen/brPBPO.css']
server = flask.Flask(__name__)
app = dash.Dash(__name__, external_stylesheets=external_stylesheets,server=server)
CACHE_CONFIG = {
    'CACHE_TYPE': 'simple',
    'CACHE_REDIS_URL': os.environ.get('REDIS_URL', 'redis://localhost:6379')
}

cache = Cache()
cache.init_app(app.server, config=CACHE_CONFIG)
TIMEOUT=86400
app.layout = html.Div([
    dcc.Store(id="date"),
    dcc.Store(id="location"),
    html.Div([
        dcc.Graph(id='graph-with-slider', hoverData={'points': [{'customdata': 'USA'}]}),
    ], style={"height": "calc(50vh - 40px)"}),
    html.Div([
        dcc.Graph(id='time-series')
    ], style={"height": "calc(50vh - 40px)"}),
    html.Div([
        dcc.Dropdown(
            id='select-area',
            options=[
                {'label':'World','value':'World'},
                {'label':'USA','value':'USA'}
            ],
            value='World',
        )
    ], style={'width': '175px', 'display': 'inline-block'}),
    html.Div([
        dcc.Dropdown(
            id='select-graph',
            options=[
                {'label': 'Scatter',    'value': 'scatter'},
                {'label': 'Choropleth', 'value': 'choropleth'}
            ],
            value=['choropleth'],
            multi=True
        )
    ], style={'width': '250px', 'display': 'inline-block'}),
    html.Div([
        dcc.Dropdown(
            id='select-data',
            options=[
                {'label': 'confirmed',    'value': 'confirmed'},
                {'label': 'deaths', 'value': 'deaths'},
                {'label': 'recovered', 'value': 'recovered'}
            ],
            value='confirmed'
        )
    ], style={'width': '125px', 'display': 'inline-block'}),
    html.Div([
        dcc.Slider(
            id='date-slider',
            min=unixTimeMillis(df['date'].min()),
            max=unixTimeMillis(df['date'].max()),
            value=unixTimeMillis(df['date'].min()),
            marks={unixTimeMillis(date):{'label':str(date.strftime('%m/%d')).lstrip('0').replace('/0','/'),'style':{'writing-mode': 'vertical-lr','text-orientation': 'sideways'}} for date in df['date']},
            step=None
        )
    ], style={'width': 'calc(100% - 550px)', 'display': 'inline-block'})

])

@app.callback(Output('date', 'data'),
             [Input('date-slider', 'value'),
              Input('select-area', 'value')])
@cache.memoize()
def df_date(date, area):
    date_parsed=datetime.fromtimestamp(date)
    temp = df_states if area == "USA" else df
    return temp.query('date==@date_parsed').to_dict('list')

@app.callback(Output('location', 'data'),
             [Input('select-data', 'value'),
              Input('select-area', 'value')])
@cache.memoize()
def df_location(data, area):
    temp = df_states.groupby('abbreviation') if area == "USA" else df.groupby('iso3')
    return temp[['date',data]].apply(lambda x: x.values.T.tolist()).to_dict()

app.clientside_callback(
    """
    function(df_by_loc, hoverData) {
        var loc_name=hoverData['points'][0]['location'] || 'USA'
        return {
            'data': [{
                'x':df_by_loc[loc_name][0],
                'y':df_by_loc[loc_name][1]
            }]
        }
    }
    """,
    Output('time-series', 'figure'),
   [Input('location', 'data'),
    Input('graph-with-slider', 'hoverData')]
)

@app.callback(Output('graph-with-slider', 'figure'),
             [Input('date', 'data'),
              Input('date-slider', 'value'),
              Input('select-graph', 'value'),
              Input('select-data', 'value')])
def update_map(df_by_date, date, graph, data):
    traces=[]
    if 'Province_State' in df_by_date:
        scope='usa'
        if 'scatter' in graph:
            traces.append({
                'type':'scattergeo',
                'locations':df_by_date['abbreviation'],
                'locationmode':'USA-states',
                'text':df_by_date['Province_State'],
                'customdata':"World"*len(df[data]),
                'marker':{'size':[x/15 for x in df_by_date[data]],'sizemode':'area','color':'red'}
            })
        if 'choropleth' in graph:
            traces.append({
                'type':'choropleth',
                'locations':df_by_date['abbreviation'],
                'locationmode':'USA-states',
                'z':df_by_date[f'{data}_rate'],
                'zmin':0,
                'zmax':1000000,
                'text':df_by_date['Province_State'],
                'customdata':"World"*len(df[data]),
                'autocolorscale':False,
                'colorscale':[[0.0, 'rgb(255,255,255)'],
                            [1e-06, 'rgb(255,245,240)'],
                            [1e-05, 'rgb(254,224,210)'],
                            [3.2e-05, 'rgb(252,187,161)'],
                            [0.0001, 'rgb(252,146,114)'],
                            [0.00032, 'rgb(251,106,74)'],
                            [0.001, 'rgb(239,59,44)'],
                            [0.01, 'rgb(203,24,29)'],
                            [0.1, 'rgb(165,15,21)'],
                            [1.0, 'rgb(103,0,13)']],
                'showscale':False
            })
    else:
        scope='world'
        if 'scatter' in graph:
            traces.append({
                'type':'scattergeo',
                'locations':df_by_date['iso3'],
                'locationmode':'ISO-3',
                'text':df_by_date['Country/Region'],
                'customdata':["USA" if x=="USA" else "World" for x in df_by_date['iso3']],
                'marker':{'size':[x/500 for x in df_by_date[data]],'sizemode':'area','color':'red'}
            })
        if 'choropleth' in graph:
            traces.append({
                'type':'choropleth',
                'locations':df_by_date['iso3'],
                'locationmode':'ISO-3',
                'z':df_by_date[f'{data}_rate'],
                'zmin':0,
                'zmax':1000000,
                'text':df_by_date['Country/Region'],
                'customdata':["USA" if x=="USA" else "World" for x in df_by_date['iso3']],
                'autocolorscale':False,
                'colorscale':[[0.0, 'rgb(255,255,255)'],
                            [1e-06, 'rgb(255,245,240)'],
                            [1e-05, 'rgb(254,224,210)'],
                            [3.2e-05, 'rgb(252,187,161)'],
                            [0.0001, 'rgb(252,146,114)'],
                            [0.00032, 'rgb(251,106,74)'],
                            [0.001, 'rgb(239,59,44)'],
                            [0.01, 'rgb(203,24,29)'],
                            [0.1, 'rgb(165,15,21)'],
                            [1.0, 'rgb(103,0,13)']],
                'showscale':False
            })
    return {
        'data': traces,
        'layout': {
            'margin':{'l':0,'r':0,'t':0,'b':0,'pad':0},
            'uirevision':True,
            'geo':{'margin':{'l':0,'r':0,'t':0,'b':0,'pad':0},
                   'uirevision':True,
                   'showland':True,
                   'landcolor':'#dddddd',
                   'showcountries':True,
                   'scope':scope,
                   'showframe': False,
                   'showcoastlines': True},
            'hovermode':'closest'
        }
    }

app.clientside_callback(
    """
    function(clickData) {
        console.log(clickData)
        if (clickData && clickData.points && clickData.points[0] && clickData.points[0].customdata)
            return clickData.points[0].customdata 
        else
            return dash.no_update
    }
    """,
    Output('select-area', 'value'),
    [Input('graph-with-slider', 'clickData')]
)

if __name__ == '__main__':
    app.run_server(debug=False)