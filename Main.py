# -*- coding: utf-8 -*-
"""
Created on Wed Jun 22 23:56:23 2022

@author: zhangi
"""

#%% Import packages
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.io as pio
import plotly.graph_objs as go
pio.renderers.default='browser' #to launch graphs in browser when running in Spyder
#%% Import Data
path = "Data.xlsx"
manager_ret = pd.read_excel(path,sheet_name='managers',parse_dates=['Date'],index_col=0)
benchmark_data = pd.read_excel(path,sheet_name='benchmarks',parse_dates=['Date'],index_col=0)
benchmark_ret = pd.DataFrame(index=benchmark_data.index.copy())
benchmark_ret=benchmark_data.pct_change()
benchmark_ret.dropna(inplace=True)
benchmark_ret['bm_O']=benchmark_ret['SPGCPMP INDEX']/2+benchmark_ret['SPGCINP INDEX']/2
benchmark_ret['bm_C']=1.7*(benchmark_ret['BXIIU3MC INDEX']-benchmark_ret['IBXXH1US INDEX']+benchmark_ret['ERIXCDIG INDEX'])

#%% annualized return/vol function

def annualize_rets(r, periods_per_year):
    """
    Annualizes a set of returns
    """
    compounded_growth = (1+r).prod()
    n_periods = r.shape[0]
    return compounded_growth**(periods_per_year/n_periods)-1

def annualize_vol(r, periods_per_year):
    """
    Annualizes the vol of a set of returns
    """
    return r.std()*(periods_per_year**0.5)
#%% Peers comparison function
def peers(sheet, manager):
#sheet = 'peers_O'
#manager = 'Manager O'

    peers_data = pd.read_excel(path,sheet_name=sheet,parse_dates=['Date'],index_col=0)
    since_inception = pd.DataFrame()
    since_inception ['# of returns'] = peers_data.count()
    since_inception ['qualified?'] = np.where(since_inception['# of returns']>=(0.75*len(peers_data.index)),since_inception['# of returns'],False)
    idx_delete = since_inception[since_inception['qualified?']==0].index
    peers_data.drop(idx_delete, inplace = True, axis = 1)
    manager_ret_M = pd.DataFrame(manager_ret[(manager)]).dropna().resample('M').apply(lambda x: ((x+1).cumprod()-1).last('D'))
    peers_data = peers_data.join(manager_ret_M,how='left') 
    ann_SR = pd.DataFrame()
    ann_SR['Returns (ann.)'] = annualize_rets(peers_data, 12)
    ann_SR['Vol (ann.)'] = annualize_vol(peers_data, 12)
    ann_SR['Sharpe Ratio (rf = 0)'] = ann_SR['Returns (ann.)']/ann_SR['Vol (ann.)']
    ann_SR['color'] = np.where(ann_SR.index ==manager, manager,'Peers')
    fig_SI = px.strip(ann_SR, y='Sharpe Ratio (rf = 0)',color = 'color', stripmode='overlay')
    fig_SI.add_trace(go.Box(y=ann_SR['Sharpe Ratio (rf = 0)'], name='Peers Ann. SR'))

    return fig_SI
#fig_SI.update_layout(autosize = False, width = 600, height = 600)


#%% Cone Chart Function

def cone(tgt_ret, tgt_vol, manager, freq):
    if freq == 'D':
        ann_factor = 252
    elif freq == 'W':
        ann_factor = 52
    elif freq == 'M':
        ann_factor = 12
    
    tgt_ret_freq = np.log(tgt_ret/ann_factor+1)
    tgt_vol_freq = tgt_vol/(ann_factor**0.5)

    cone_data = pd.DataFrame(manager_ret[(manager)]).dropna().resample(freq).apply(lambda x: ((x+1).cumprod()-1).last('D'))
    cone_data.insert(0,'count',range(1,1+len(cone_data)))
    cone_data['Return (Ln)'] = np.log(cone_data[(manager)]+1)
    cone_data['Cuml. Return'] = cone_data['Return (Ln)'].cumsum()
    cone_data['Target Return'] = tgt_ret_freq * cone_data['count']
    cone_data['Std Dev -'] = cone_data['Target Return']-tgt_vol_freq*(cone_data['count']**0.5)
    cone_data['Std Dev +'] = cone_data['Target Return']+tgt_vol_freq*(cone_data['count']**0.5)
    cone_data['Std Dev -x2'] = cone_data['Target Return']-tgt_vol_freq*(cone_data['count']**0.5)*2
    cone_data['Std Dev +x2'] = cone_data['Target Return']+tgt_vol_freq*(cone_data['count']**0.5)*2
    realized_ret = cone_data['Return (Ln)'].sum()/len(cone_data['Return (Ln)'])*ann_factor
    realized_vol = cone_data['Return (Ln)'].std()*(ann_factor**0.5)
    cone_chart = px.line(cone_data, x=cone_data.index, y=['Cuml. Return','Target Return','Std Dev -','Std Dev +','Std Dev -x2','Std Dev +x2'], title="Expected vs. Realized Return (Ln)")

    summary = pd.DataFrame(index=[1])
    summary['Start Date']=cone_data.index[0].strftime('%m/%d/%Y')
    summary['End Date']=cone_data.index[-1].strftime('%m/%d/%Y')
    summary['Expected Return (ann.)']="{:.1%}".format(tgt_ret)  
    summary['Realized Return (ann.)']="{:.1%}".format(realized_ret)
    summary['Expected Vol (ann.)']="{:.1%}".format(tgt_vol)
    summary['Realized Vol (ann.)']="{:.1%}".format(realized_vol)
    #summary.set_index('Start Date',inplace=True)
    
    return cone_chart,summary

#%% benchmark

def rolling_beta(manager, benchmark, freq, period):
#manager = 'Manager O'
#benchmark = 'bm_O'
#freq = 'W'
#period = 52

    beta_roll=pd.merge(manager_ret[manager],benchmark_ret[benchmark],left_index=True, right_index=True)
    beta_roll = beta_roll.dropna().resample(freq).apply(lambda x: ((x+1).cumprod()-1).last('D'))
    beta_roll['cov']=beta_roll[manager].rolling(period).cov(beta_roll[benchmark])
    beta_roll['bm_var']=beta_roll[benchmark].rolling(period).var()
    beta_roll['Rolling '+str(period)+freq+' beta']=beta_roll['cov']/beta_roll['bm_var']
    chart_data = beta_roll['Rolling '+str(period)+freq+' beta'].dropna()

    beta_chart = px.line(chart_data, x=chart_data.index, y=['Rolling '+str(period)+freq+' beta'], title='Rolling '+str(period)+freq+' beta')

    return beta_chart

#%% Streamlit Web App
#managers = list(df['Ticker'].unique()
st.title("Managers Monitoring")
managerPick = st.sidebar.selectbox("Pick the manager to monitor",['Manager O','Manager C'])
if managerPick =='Manager O':
    cone_O,summary_O=cone(0.09,0.06,'Manager O','W')
    beta_O = rolling_beta('Manager O','bm_O','W',52)
    peers_O = peers('peers_O','Manager O')
    st.subheader("Standalone Performance")
    st.plotly_chart(cone_O)
    st.table(summary_O)
    st.subheader("Factor Monitoring")
    st.plotly_chart(beta_O)
    bm_summary = pd.DataFrame(index=[1])
    bm_summary['Index']='SPGCPMP Index + SPGCINP Index'
    bm_summary['Index Description']='50% S&P GSCI Precious Metals Official Close Index + 50% S&P GSCI Industrial Metals Official Close Index'
    st.table(bm_summary)
    st.subheader("Peers Comparison")
    st.plotly_chart(peers_O)
    
    
elif managerPick =='Manager C':
    cone_C, summary_C = cone(0.065,0.06,'Manager C','W')
    beta_C = rolling_beta('Manager C','bm_C','W',52)
    peers_C = peers('peers_C','Manager C')
    st.subheader("Standalone Performance")
    st.plotly_chart(cone_C)
    st.table(summary_C)
    st.subheader("Factor Monitoring")
    st.plotly_chart(beta_C)
    bm_summary = pd.DataFrame(index=[1])
    bm_summary['Index']='BXIIU3MC Index - IBXXH1US Index + ERIXCDIG Index'
    bm_summary['Index Description']='Long cash (LIBOR), short IBOXIG (duration-hedged), selling protection on CDX IG total return index. Factor is notional weighted and vol-adjusted'
    st.table(bm_summary)
    st.subheader("Peers Comparison")
    st.plotly_chart(peers_C)