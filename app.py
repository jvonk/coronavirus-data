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