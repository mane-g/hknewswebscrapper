from bs4 import BeautifulSoup
import concurrent.futures as con
from collections import defaultdict
import lxml
import pandas as pd
import requests
import re


MAIN_URL = r'https://www.hkexnews.hk/sdw/search/searchsdw.aspx'
QUERY_URL = r'https://www3.hkexnews.hk/sdw/search/searchsdw.aspx'


def _perform_webscrap(query_date: pd.Timestamp, stock_code: str) -> pd.DataFrame:
    res=requests.get(MAIN_URL)
    bsl = BeautifulSoup(res.text, "lxml")
    __VIEWSTATEGENERATOR = bsl.find("input", {"id": "__VIEWSTATEGENERATOR"}).attrs['value']
    __VIEWSTATE = bsl.find("input", {"id": "__VIEWSTATE"}).attrs['value']
    today = bsl.find("input", {"id": "today"}).attrs['value']
    data = {
        "__EVENTTARGET": "btnSearch",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": __VIEWSTATE,
        "__VIEWSTATEGENERATOR": __VIEWSTATEGENERATOR,
        "today": today,
        "sortBy": "shareholding",
        "sortDirection": "desc",
        "alertMsg": "",
        "txtShareholdingDate": query_date.strftime("%Y/%m/%d"),
        "txtStockCode": stock_code,
        "txtStockName": "",
        "txtParticipantID": "",
        "txtParticipantName": "",
        "txtSelPartID": ""
    }

    req = requests.post(QUERY_URL, data=data)
    soup = BeautifulSoup(req.content, 'html.parser')

    headers = [th.text.strip() for th in soup.find_all('th')]
    values = [[td.find(attrs={'class': re.compile('body')}).text for td in tr.find_all('td')] for tr in soup.find_all('tr')[1:]]
    df = pd.DataFrame(values, columns=headers)
    if df.empty:
        return df
    df['Date'] = query_date.date()
    df['Holdings'] = df[r'% of the total number of Issued Shares/ Warrants/ Units'].str.strip('%').astype('float')
    df['Participant Name'] = df[r'Name of CCASS Participant(* for Consenting Investor Participants )']
    return df[["Date", "Participant ID", "Participant Name", "Shareholding", "Holdings"]]


def _get_shareholding(start_date: str, end_date: str, stock_code: str) -> pd.DataFrame:
    final_df = pd.DataFrame()
    with con.ThreadPoolExecutor(max_workers=8) as exc:
        fut_list = []
        for dt in pd.date_range(start_date, end_date):
            future = exc.submit(_perform_webscrap, dt, stock_code)
            fut_list.append(future)

        for f in con.as_completed(fut_list):  # Blocks till the result is not available
            res = f.result()  # Get result from the future, BLOCKING. But non-blocking here because of as_completed
            if res.empty:
                continue
            final_df = final_df.append(res)
    return final_df


def get_shareholding_trend(start_date: str, end_date: str, stock_code: str, max_holders: int = 10) -> dict:
    res = _get_shareholding(start_date, end_date, stock_code)
    res['Date'] = res['Date'].apply(lambda dt: dt.strftime("%Y-%m-%d"))
    res = res.set_index('Date')
    top_holders_asof = res.loc[end_date].iloc[:max_holders]['Participant ID']
    res = res[res['Participant ID'].isin(top_holders_asof)]

    desc_order = res.loc[end_date].sort_values('Holdings', ascending=False)['Participant ID']
    desc_dict = {val: index for index, val in enumerate(desc_order)}
    res_dict = defaultdict(dict)
    for index in sorted(res.index.unique(), reverse=True):
        temp_df = res.loc[index].sort_values(by=['Participant ID'], key=lambda x: x.map(desc_dict))
        res_dict[index]['Participant ID'] = list(temp_df['Participant ID'])
        res_dict[index]['Holdings'] = list(temp_df['Holdings'])
        res_dict[index]['Participant Name'] = list(temp_df['Participant Name'])
        res_dict[index]['Shareholding'] = list(temp_df['Shareholding'])
    return res_dict


def get_transactions(start_date: str, end_date: str, stock_code: str, threshold: float) -> dict:
    res = _get_shareholding(start_date, end_date, stock_code)
    res['Date'] = res['Date'].apply(lambda dt: dt.strftime("%Y-%m-%d"))
    res = res.reset_index(drop=True)
    res['Diff'] = res.sort_values('Date').groupby('Participant ID', as_index=False)['Holdings'].diff()
    res.loc[res['Date'] == start_date, 'Diff'] = 0.0
    res['Diff'].fillna(res['Holdings'], inplace=True)

    res = res.round(2)
    res_dict = defaultdict(list)
    transactions_df = res[abs(res['Diff']) >= threshold]
    for dt in pd.date_range(start_date, end_date)[1:]:
        dt = dt.strftime("%Y-%m-%d")
        trans_df = transactions_df[transactions_df['Date'] == dt]
        trans_df = trans_df.merge(trans_df, how='cross')
        trans_df = trans_df[(trans_df['Diff_x'] > 0) & (trans_df['Diff_y'] < 0)]
        trans_df['Exchanged'] = trans_df[['Diff_y', 'Diff_x']].abs().min(axis=1)
        res_dict[dt] = list(trans_df.itertuples(index=False, name=None))
    return res_dict