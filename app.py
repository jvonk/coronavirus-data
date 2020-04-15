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

df = pd.read_pickle('df.pkl')
unixTimeMillis = lambda dt: int(time.mktime(dt.timetuple()))
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

server = flask.Flask(__name__)
app = dash.Dash(__name__, external_stylesheets=external_stylesheets,server=server)
app.layout = html.Div([
    html.Div([
        dcc.Graph(id='graph-with-slider', hoverData={'points': [{'customdata': 'USA'}]}),
        dcc.Store(
            id='clientside-figure-store',
            data=df.to_dict('records')
        )
    ], style={"height": "40%"}),
    html.Div([
        dcc.Graph(id='time-series')
    ], style={"height": "40%"}),
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
    ], style={'width': 'calc(100% - 400px)', 'display': 'inline-block'})

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
            'layout': {
            'uirevision':true,
            "shapes":[
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

app.clientside_callback(
    """
    function(df, date, graphs, data) {
        temp=Math.round((new Date(date*1000)-new Date(df[0].date))/86400000);
        arr=df.reduce(function(ind, el, i) { 
                    if (el.days==temp) 
                        ind.push(el); 
                    return ind; 
                }, []);
        var map = {};
        for (var i = 0; i < arr.length; ++i) {
            for (var key in arr[i]) {
                if (!map[key])
                    map[key]=[]
                if (key==data)
                    map[key].push(arr[i][key]/300)
                else
                    map[key].push(arr[i][key])
            }
        }
        var traces = [];
        if (graphs.includes('scatter')) {
            traces.push({
                'type':'scattergeo',
                'locations':map['iso3'],
                'text':map['Country/Region'],
                'customdata':map['iso3'],
                'marker':{'size':map[data],'sizemode':'area','color':'red'}
            })
        }
        if (graphs.includes('choropleth')) {
            traces.push({
                'type':'choropleth',
                'locations':map['iso3'],
                'z':map[data+'_rate'],
                'zmin':0,
                'zmax':1000000,
                'text':map['Country/Region'],
                'customdata':map['iso3'],
                'autocolorscale':false,
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
                'showscale':false
            })
        }
        return {
            'data': traces,
            'layout': {
                'uirevision':true,
                'geo':{'scope':'world', 'showframe': true, 'showcoastlines': true,},
                'hovermode':'closest'
            }
        }
    }
    """,
    Output('graph-with-slider', 'figure'),
    [Input('clientside-figure-store', 'data'),
     Input('date-slider', 'value'),
     Input('select-graph', 'value'),
     Input('select-data', 'value')]
)
if __name__ == '__main__':
    app.run_server(debug=True)
