import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import plotly
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import imageio
import json
import pycountry
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import requests
import time
from urllib.parse import quote

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

df_confirmed = transform_and_standardize(pd.read_csv(INPUT_URL+"csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"), 'confirmed')
df_deaths = transform_and_standardize(pd.read_csv(INPUT_URL+"csse_covid_19_time_series/time_series_covid19_deaths_global.csv"), 'deaths')
df_recovered = transform_and_standardize(pd.read_csv(INPUT_URL+"csse_covid_19_time_series/time_series_covid19_recovered_global.csv"), 'recovered')
df = df_confirmed.merge(df_deaths,how='outer',on=['date', 'iso3', 'Population','Country/Region']).merge(df_recovered,how='outer',on=['date', 'iso3', 'Population','Country/Region'])
for col in ['confirmed', 'deaths', 'recovered']:
    df[f'{col}_rate'] = (df[col]/df['Population']*100000000).astype('int64')
df['days']=[(date-df['date'][0]).days for date in df['date']]

unixTimeMillis = lambda dt: int(time.mktime(dt.timetuple()))

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server=app.server
dff=df[df['iso3'] == 'USA']
app.layout = html.Div([
    html.Div([
        dcc.Graph(id='graph-with-slider', hoverData={'points': [{'customdata': 'USA'}]}),
        dcc.Store(
            id='clientside-figure-store',
            data=df.to_dict('records')
        )
    ], style={'width': '49%', 'display': 'inline-block', 'padding': '0 20'}),
    html.Div([
        dcc.Graph(id='time-series')
    ], style={'width': '49%', 'display': 'inline-block'}),
    dcc.Dropdown(
        id='select-graph',
        options=[
            {'label': 'Scatter',    'value': 'scatter'},
            {'label': 'Choropleth', 'value': 'choropleth'}
        ],
        value=['choropleth'],
        multi=True
    ),    
    dcc.Dropdown(
        id='select-data',
        options=[
            {'label': 'confirmed',    'value': 'confirmed'},
            {'label': 'deaths', 'value': 'deaths'},
            {'label': 'recovered', 'value': 'recovered'}
        ],
        value='confirmed'
    ),
    dcc.Slider(
        id='date-slider',
        min=unixTimeMillis(df['date'].min()),
        max=unixTimeMillis(df['date'].max()),
        value=unixTimeMillis(df['date'].min()),
        marks={unixTimeMillis(date):{'label':str(date.strftime('%m/%d')).lstrip('0').replace('/0','/'),'style':{'writing-mode': 'vertical-lr','text-orientation': 'sideways'}} for date in df['date']},
        step=None
    )
])

app.clientside_callback(
    """
    function(hoverData, df, date, graph, data) {
        iso_name = hoverData.points[0].customdata
        temp=Math.round((new Date(date*1000)-new Date(df[0].date))/86400000);
        arr=df.reduce(function(ind, el, i) { 
                    if (el.iso3==iso_name) 
                        ind.push(el); 
                    return ind; 
                }, []);
        filter=arr.reduce(function(ind, el, i) { 
                    if (el.days==temp) 
                        ind.push(el); 
                    return ind; 
                }, []);
        var map = {};
        for (var i = 0; i < arr.length; ++i) {
            for (var key in arr[i]) {
                if (!map[key])
                    map[key]=[]
                map[key].push(arr[i][key])
            }
        }
        var fmap = {};
        for (var i = 0; i < filter.length; ++i) {
            for (var key in filter[i]) {
                fmap[key]=filter[i][key]
            }
        }
        return {
            'data': [{
                'x':map.date,
                'y':map[data]
            }],
            'layout': {"shapes":[
                {
                    "type":"line",
                    "xref":"x",
                    "yref":"paper",
                    "x0":fmap.date,
                    "y0":0,
                    "x1":fmap.date,
                    "y1":1,
                    "line":{
                        "color":"Black",
                        "dash":"dot"
                    }
                },{
                    "type":"line",
                    "xref":"paper",
                    "yref":"y",
                    "x0":0,
                    "y0":fmap[data],
                    "x1":1,
                    "y1":fmap[data],
                    "line":{
                        "color":"Black",
                        "dash":"dot"
                    }
                }
            ]}
        };
    }
    """,
    Output('time-series', 'figure'),
    [Input('graph-with-slider', 'hoverData'),
     Input('clientside-figure-store', 'data'),
     Input('date-slider', 'value'),
     Input('select-graph', 'value'),
     Input('select-data', 'value')]
)

@app.callback(Output('graph-with-slider', 'figure'), [Input('date-slider', 'value'),Input('select-graph', 'value'),Input('select-data', 'value')])
def update_figure(date,graphs,data):
    filtered_df = df[df["date"] == datetime.fromtimestamp(date)]
    traces=[]
    if 'scatter' in graphs:
        traces.append(go.Scattergeo(
            locations=filtered_df['iso3'],
            text=filtered_df['Country/Region'],
            customdata=filtered_df['iso3'],
            marker={'size':filtered_df[data]/300,'sizemode':'area','color':'red'}
        ))
    if 'choropleth' in graphs:
        traces.append(go.Choropleth(
            locations=filtered_df['iso3'],
            z=filtered_df[f'{data}_rate'],
            zmin=0,
            zmax=1000000,
            text=filtered_df['Country/Region'],
            customdata=filtered_df['iso3'],
            autocolorscale=False,
            colorscale=[[0.0, 'rgb(255,255,255)'],
                        [1e-06, 'rgb(255,245,240)'],
                        [1e-05, 'rgb(254,224,210)'],
                        [3.2e-05, 'rgb(252,187,161)'],
                        [0.0001, 'rgb(252,146,114)'],
                        [0.00032, 'rgb(251,106,74)'],
                        [0.001, 'rgb(239,59,44)'],
                        [0.01, 'rgb(203,24,29)'],
                        [0.1, 'rgb(165,15,21)'],
                        [1.0, 'rgb(103,0,13)']]
        ))
    return {
        'data': traces,
        'layout': dict(
            uirevision = True,
            geo = {'scope':'world', 'showframe': True, 'showcoastlines': True},
            hovermode='closest'
        )
    }

"""
@app.callback(
    dash.dependencies.Output('time-series', 'figure'),
    [dash.dependencies.Input('graph-with-slider', 'hoverData'),Input('date-slider', 'value'),Input('select-graph', 'value'),Input('select-data', 'value')])
def update_timeseries(hoverData,date,graphs,data):
    iso_name = hoverData['points'][0]['customdata']
    dff = df[df['iso3'] == iso_name]
    filter_dff=dff[dff["date"] == datetime.fromtimestamp(date)]
    print(dff[dff["date"] == datetime.fromtimestamp(date)]['year'])
    return {
        'data': [dict(
            x=dff['days'],
            y=dff[data]
        )],
        'layout': dict(shapes=[
            dict(
                type="line",
                xref="x",
                yref="paper",
                x0=filter_dff['days'],
                y0=0,
                x1=filter_dff['days'],
                y1=1,
                line=dict(
                    color="Black",
                    dash="dot"
                )
            ),dict(
                type="line",
                xref="paper",
                yref="y",
                x0=0,
                y0=int(filter_dff[data]),
                x1=1,
                y1=int(filter_dff[data]),
                line=dict(
                    color="Black",
                    dash="dot"
                )
            )
        ])
    }

app
"""
if __name__ == '__main__':
    app.run_server(debug=True)