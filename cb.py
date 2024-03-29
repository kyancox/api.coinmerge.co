from coinbase.wallet.client import Client
from coinbase.wallet.error import APIError
import pprint
from portfolioClass import Portfolio

# Coinbase API V2

def coinbasePortfolio(api_key, api_secret):
    
    client = Client(api_key, api_secret)


    accounts = client.get_accounts(limit='100')
    # https://stackoverflow.com/questions/67343099/coinbase-api-btc-account-missing
    # https://forums.coinbasecloud.dev/t/client-get-accounts-only-gives-certain-cryptos-for-output/890/4

    data = accounts.data

    #accounts = {key.balance.currency:[key.currency.name, key.balance.amount] for key in data} 
    accounts = {key.balance.currency:key.balance.amount for key in data}

    return Portfolio("Coinbase", accounts)


