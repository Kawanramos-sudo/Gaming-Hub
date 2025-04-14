import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET
from database_UPD import connect
from bs4 import BeautifulSoup
import re
from colorama import Fore, Style, init
import webbrowser
import threading
import sys
import concurrent.futures
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# Inicializa o colorama
init(autoreset=True)

# Credenciais da Green Man Gaming (Impact API)
import os

account_sid = os.getenv("ACCOUNT_SID")
auth_token = os.getenv("AUTH_TOKEN")
catalog_id = os.getenv("CATALOG_ID")


@dataclass
class Game:
    id: int
    name: str
    green_man_nome: Optional[str]
    steam_url: Optional[str]
    instant_url: Optional[str]
    nuuvem_url: Optional[str]
    cdkeys_url: Optional[str]
    yuplay_url: Optional[str]

class PriceUpdater:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        })

    def get_yuplay_price(self, url: str) -> Optional[float]:
        """Obtém o preço convertido da YUPLAY."""
        try:
            if not url:
                return None

            response = self.session.get(url)
            if response.status_code != 200:
                print(f"{Fore.RED}Erro ao acessar a página YUPLAY: {response.status_code}{Style.RESET_ALL}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            out_of_stock = soup.find('button', class_='button small-button text-uppercase m-r-0-8', disabled=True)
            if out_of_stock:
                print(f"{Fore.YELLOW}Jogo fora de estoque na YUPLAY: {url}{Style.RESET_ALL}")
                return 0.00
            
            preco_elemento = soup.find('span', class_='catalog-item-sale-price')
            if not preco_elemento:
                return None
            
            preco_texto = preco_elemento.get_text(strip=True).replace('$', '')
            preco_dolar = float(preco_texto)
            
            # Cache da taxa de câmbio para evitar múltiplas requisições
            if not hasattr(self, 'taxa_cambio'):
                response = self.session.get('https://api.exchangerate-api.com/v4/latest/USD')
                if response.status_code == 200:
                    dados_cambio = response.json()
                    self.taxa_cambio = dados_cambio.get('rates', {}).get('BRL')
                else:
                    return None
            
            preco_real = preco_dolar * self.taxa_cambio
            return round(preco_real, 2)
        except Exception as e:
            print(f"{Fore.RED}Erro ao obter preço da YUPLAY: {e}{Style.RESET_ALL}")
            return None

    def get_cdkeys_price(self, url: str) -> Tuple[Optional[float], Optional[bool]]:
        try:
            response = self.session.get(url)
            if response.status_code != 200:
                return None, None

            soup = BeautifulSoup(response.text, "html.parser")

            out_of_stock = soup.find("div", class_="product-usps-item attribute attribute stock unavailable")
            if out_of_stock:
                return 0.00, True

            price_tag = soup.find("span", class_="price")
            if price_tag:
                price_text = price_tag.text.strip().replace("R$", "").replace(",", ".")
                return float(price_text), False

            return None, False
        except Exception:
            return None, None

    def get_nuuvem_price(self, url: str) -> Optional[float]:
        try:
            if not url or url.lower() == 'na':
                return None
            
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            price_container = soup.find('span', class_='product-price--val')
            if price_container:
                integer_part = price_container.find('span', class_='integer').text.strip()
                decimal_part = price_container.find('span', class_='decimal').text.strip()
                price = f"{integer_part}.{decimal_part}".replace('.,', '.')
                return float(price)
            
            return None
        except Exception:
            return None

    def get_steam_price(self, game_id: int, url: str) -> Optional[float]:
        try:
            if not url or 'steam' not in url:
                return None
            app_id = url.split('/')[4]
            if not app_id.isdigit():
                return None
            
            api_url = f'https://store.steampowered.com/api/appdetails?appids={app_id}&cc=br'
            response = self.session.get(api_url)
            if response.status_code == 200:
                data = response.json()
                if data[str(app_id)]['success']:
                    price_data = data[str(app_id)]['data'].get('price_overview')
                    if price_data and price_data['currency'] == 'BRL':
                        return price_data['final'] / 100
            return None
        except Exception:
            return None

    def get_green_man_gaming_price(self, catalog_item_id: str) -> Optional[float]:
        try:
            if not catalog_item_id:
                return None
                
            base_url = f'https://api.impact.com/Mediapartners/{account_sid}/Catalogs/{catalog_id}/Items'
            params = {'PageSize': 100, 'Query': f"CatalogItemId = '{catalog_item_id}'"}
            response = self.session.get(
                base_url, 
                auth=HTTPBasicAuth(account_sid, auth_token), 
                params=params
            )
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                items = root.findall('.//Items')
                
                if items and items[0].findall('Item'):
                    for item in items[0].findall('Item'):
                        price = item.find('CurrentPrice').text or None
                        return float(price) if price else None
            
            return None
        except Exception:
            return None
def get_instant_gaming_price(self, url: str) -> Optional[float]:
    try:
        if not url or url.lower() == 'na':
            return None

        response = self.session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Salvar HTML para depuração no GitHub Actions
        with open("instant_gaming_debug.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())

        stock_status = soup.find('div', class_='nostock')
        if stock_status and 'fora de stock' in stock_status.text.lower():
            print(f"❌ Jogo fora de estoque na Instant Gaming: {url}")
            return 0

        price_div = soup.find('div', class_='total')
        if price_div:
            raw_price = price_div.text.strip()
            match = re.search(r"R\$\s?([\d,.]+)", raw_price)
            if match:
                return float(match.group(1).replace(',', '.'))

        print(f"⚠️ Nenhum preço encontrado na Instant Gaming para {url}")
        return None
    except Exception as e:
        print(f"❌ Erro ao obter preço da Instant Gaming: {e}")
        return None

def update_game_price_in_db(cursor, game_id: int, store_name: str, price: float) -> None:
    try:
        cursor.execute("""
            INSERT INTO game_prices (game_id, store_name, price)
            VALUES (%s, %s, %s)
            ON CONFLICT (game_id, store_name)
            DO UPDATE SET price = EXCLUDED.price;
        """, (game_id, store_name, price))
        print(f"{Fore.GREEN}Jogo {game_id} - Loja {store_name} - Preço atualizado: {price}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Erro ao atualizar preço no banco de dados: {e}{Style.RESET_ALL}")


def process_store_price(cursor, updater: PriceUpdater, game: Game, store_info: Dict[str, Any]) -> None:
    store_name = store_info['name']
    url = store_info.get('url')
    price = None

    if store_name == 'Green Man Gaming' and game.green_man_nome:
        price = updater.get_green_man_gaming_price(game.green_man_nome)
    elif store_name == 'Steam' and url:
        price = updater.get_steam_price(game.id, url)
    elif store_name == 'Instant Gaming' and url and url.lower() != 'na':
        price = updater.get_instant_gaming_price(url)
    elif store_name == 'Nuuvem' and url and url.lower() != 'na':
        price = updater.get_nuuvem_price(url)
    elif store_name == 'Cd Keys' and url and url.lower() != 'na':
        price, out_of_stock = updater.get_cdkeys_price(url)
        if out_of_stock:
            price = 0.00
    elif store_name == 'YUPLAY' and url and url.lower() != 'na':
        price = updater.get_yuplay_price(url)

    if price is not None:
        update_game_price_in_db(cursor, game.id, store_name, price)


def update_prices() -> None:
    print(f"{Fore.CYAN}Iniciando atualização de preços...{Style.RESET_ALL}")

    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT DISTINCT 
                g.id, 
                g.name, 
                g.green_man_nome, 
                (SELECT url FROM game_prices WHERE game_id = g.id AND store_name = 'Steam') as steam_url,
                (SELECT url FROM game_prices WHERE game_id = g.id AND store_name = 'Instant Gaming') as instant_url,
                (SELECT url FROM game_prices WHERE game_id = g.id AND store_name = 'Nuuvem') as nuuvem_url,
                (SELECT url FROM game_prices WHERE game_id = g.id AND store_name = 'Cd Keys') as cdkeys_url,
                (SELECT url FROM game_prices WHERE game_id = g.id AND store_name = 'YUPLAY') as yuplay_url
            FROM games g
        """)
        games = [Game(*row) for row in cursor.fetchall()]

        updater = PriceUpdater()

        for game in games:
            print(f"\n{Fore.YELLOW}Processando {game.name}...{Style.RESET_ALL}")

            stores = [
                {'name': 'Green Man Gaming', 'url': None},
                {'name': 'Steam', 'url': game.steam_url},
                {'name': 'Instant Gaming', 'url': game.instant_url},
                {'name': 'Nuuvem', 'url': game.nuuvem_url},
                {'name': 'Cd Keys', 'url': game.cdkeys_url},
                {'name': 'YUPLAY', 'url': game.yuplay_url}
            ]

            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [
                    executor.submit(process_store_price, cursor, updater, game, store)
                    for store in stores
                ]
                concurrent.futures.wait(futures)

        conn.commit()  # Commit no final, evitando commits repetidos
    except Exception as e:
        print(f"{Fore.RED}Erro durante a atualização de preços: {e}{Style.RESET_ALL}")
    finally:
        cursor.close()
        conn.close()
        print(f"\n{Fore.GREEN}Atualização de preços concluída!{Style.RESET_ALL}")


if __name__ == "__main__":
    update_prices()
    sys.exit()