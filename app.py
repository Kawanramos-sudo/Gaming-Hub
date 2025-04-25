from flask import Flask, request, render_template, abort, session, jsonify
import psycopg2
from flask_caching import Cache
from database import get_write_connection, release_connection, get_read_connection
from decimal import Decimal
import requests
import json
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from psycopg2.extras import DictCursor
from psycopg2 import sql
from markupsafe import escape
from flask_talisman import Talisman
import os
from datetime import datetime


app = Flask(__name__, template_folder=os.path.abspath('.'))

import time

_cached_games = {
    "data": [],
    "last_updated": 0
}

CACHE_DURATION = 300  # 5 minutos

def get_cached_games():
    now = time.time()

    # Se o cache estiver válido, retorna ele
    if now - _cached_games["last_updated"] < CACHE_DURATION:
        return _cached_games["data"]

    # Se expirou, atualiza
    fresh_games = get_games_from_db()
    for game in fresh_games:
        game["links"] = sorted(
            game["links"], 
            key=lambda x: x["price"] if x["price"] is not None else float('inf')
        )
        game["lowest_price"] = get_lowest_price(game)

    # Atualiza o cache manual
    _cached_games["data"] = fresh_games
    _cached_games["last_updated"] = now

    return fresh_games


import re


def get_genres_from_db():
    conn = None
    try:
        conn = get_read_connection()
        if not conn:
            return []

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT unnest(string_to_array(genres, ',')) as genre
                FROM games 
                WHERE genres IS NOT NULL
            """)
            return sorted({row[0].strip() for row in cursor.fetchall() if row[0]})

    except Exception as e:
        app.logger.error(f"Erro ao obter gêneros: {e}")
        return []
    finally:
        if conn:
            release_connection(conn)  # Remove o conn.close() redundante





def is_valid_url(url):
    """Verifica se a URL é válida."""
    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// ou https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domínio
        r'localhost|' # ou localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|' # ou IP
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)' # ou IP v6
        r'(?::\d+)?' # Porta opcional
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def get_games_from_db():
    conn = None  # 🔹 Garante que a variável `conn` sempre exista

    try:
        conn = get_read_connection()
        if not conn:
            print("Erro: Não foi possível conectar ao banco de dados.")
            return []

        with conn.cursor() as cursor:
            query = """
            SELECT 
                g.id, g.name, g.description, g.genres, g.release_date, 
                g.image, g.images, g.green_man_nome, g.popularity, 
                gp.store_name, gp.price, gp.url
            FROM 
                games g
            LEFT JOIN 
                game_prices gp 
            ON 
                g.id = gp.game_id
            """
            cursor.execute(query)
            rows = cursor.fetchall()

        games = {}
        for row in rows:
            game_id, name, description, genres, release_date, image, images, green_man_nome, popularity, store_name, price, url = row

            if game_id not in games:
                games[game_id] = {
                    "id": game_id, "name": name or "Nome não disponível",
                    "description": description or "Descrição não disponível",
                    "genres": genres, "release_date": release_date or "Data não disponível",
                    "image": image or "", "images": json.loads(images) if isinstance(images, str) else [],
                    "green_man_nome": green_man_nome, "popularity": popularity,
                    "links": [],
                    "lowest_price": None  # 🔹 Sempre adiciona a chave
                }

            if store_name and url and price and price > 0:
                games[game_id]["links"].append({"store": store_name, "price": price, "url": url})

                # 🔹 Atualiza o menor preço
                if games[game_id]["lowest_price"] is None or price < games[game_id]["lowest_price"]:
                    games[game_id]["lowest_price"] = price

        return list(games.values())

    except Exception as e:
        print(f"Erro ao buscar jogos do banco: {e}")
        return []
    
    finally:
        if conn is not None:  # 🔹 Evita erro caso `conn` não tenha sido inicializada
            release_connection(conn)




def increase_popularity(game_id):
    conn = None
    try:
        conn = get_write_connection()
        if not conn:
            print("Erro: Não foi possível obter conexão de escrita")
            return None

        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE games
                SET popularity = popularity + 1
                WHERE id = %s
                RETURNING popularity;
            """, (game_id,))
            
            new_popularity = cursor.fetchone()
            
            if new_popularity:
                conn.commit()
                return new_popularity[0]
            
            # Se não encontrou o jogo, faz rollback
            conn.rollback()
            return None
            
    except Exception as e:
        # Garante rollback em caso de erro
        if conn:
            conn.rollback()
        print(f"Erro ao aumentar a popularidade do jogo {game_id}: {str(e)}")
        return None
        
    finally:
        # Libera a conexão de volta ao pool correto
        if conn:
            release_connection(conn)  # Ou (conn) se for genérico








def get_game_by_id(game_id):
    conn = None
    try:
        conn = get_read_connection()
        if not conn:
            app.logger.error("Erro: Não foi possível obter conexão do pool")
            return None

        with conn.cursor() as cursor:
            # Consulta principal
            cursor.execute("""
                SELECT id, name, description, genres, release_date, 
                       image, images, green_man_nome, popularity, tumb
                FROM games WHERE id = %s
            """, (game_id,))
            game = cursor.fetchone()

            if not game:
                return None

            # Processamento dos dados...
        # Processamento robusto das imagens
        raw_images = game[6]  # Campo images
        image_list = []
        
        if raw_images:
            try:
                # Caso 1: String JSON (ex: "[\"url1.jpg\", \"url2.jpg\"]")
                if isinstance(raw_images, str) and raw_images.strip().startswith('['):
                    image_list = json.loads(raw_images)
                
                # Caso 2: Array PostgreSQL (convertido para lista pelo psycopg2)
                elif isinstance(raw_images, list):
                    image_list = raw_images
                
                # Caso 3: String com URLs separadas por vírgula
                elif isinstance(raw_images, str):
                    image_list = [url.strip() for url in raw_images.split(',') if url.strip()]
                
                # Filtra apenas URLs válidas
                image_list = [url for url in image_list if url.startswith(('http://', 'https://'))]
                
            except Exception as e:
                print(f"Erro ao processar imagens do jogo {game_id}: {str(e)}")
                image_list = []

            # Consulta preços em uma única query com JOIN
            cursor.execute("""
                SELECT store_name, price, url 
                FROM game_prices 
                WHERE game_id = %s AND price > 0 AND url IS NOT NULL
                ORDER BY price
            """, (game_id,))
            
            store_links = [{
                "store": store,
                "price": price,
                "url": url
            } for store, price, url in cursor.fetchall()]

            return {
                "id": game[0],
                "name": game[1],
                "description": game[2],
                "genres": game[3],
                "release_date": str(game[4]),
                "image": game[5],
                "images": image_list,
                "green_man_nome": game[7],
                "popularity": game[8],  # Removida a chamada para increase_popularity()
                "tumb": game[9],
                "links": store_links
            }

    except Exception as e:
        app.logger.error(f"Erro ao buscar jogo {game_id}: {str(e)}")
        return None
    finally:
        if conn:
            release_connection(conn)  # Consistente com get_read_connection()






def get_cheapest_games():
    conn = get_read_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT g.id, g.name, g.image, MIN(p.price) AS lowest_price
                FROM games g
                JOIN game_prices p ON g.id = p.game_id
                WHERE p.price > 0
                GROUP BY g.id, g.name, g.image
                ORDER BY lowest_price ASC
                LIMIT 15;
            """)
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "image": row[2],
                    "lowest_price": row[3]
                }
                for row in cursor.fetchall()
            ]
    except Exception as e:
        print(f"Erro ao buscar os jogos mais baratos: {e}")
        return []
    finally:
        release_connection(conn)




# Função para calcular o menor preço
def get_lowest_price(game):
    if not game.get("links"):
        return None
    
    try:
        # Filtra e converte preços válidos
        valid_prices = [
            Decimal(str(link["price"])) 
            for link in game["links"] 
            if link.get("price") is not None
        ]
        
        return str(min(valid_prices)) if valid_prices else None
    except Exception as e:
        app.logger.error(f"Erro ao calcular menor preço: {e}")
        return None




# Lista de jogos
# Exemplo de como organizar a lógica de busca e API
games = get_games_from_db()
for game in games:
    game["links"] = sorted(game["links"], key=lambda x: x["price"] if x["price"] is not None else float('inf'))
    game["lowest_price"] = get_lowest_price(game)

# Atualizar o preço mais baixo para cada jogo
# Atualizar o preço mais baixo para cada jogo







# Ícones das lojas
store_icons = {
    "Steam": "https://i.ibb.co/x8FkBLk7/steam-logo-6.png",
    "GOG": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/GOG.com_logo_no_URL.svg/640px-GOG.com_logo_no_URL.svg.png",
    "Humble Bundle": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Humble_Bundle_H_logo_red.svg/640px-Humble_Bundle_H_logo_red.svg.png",
    "Gamivo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/GAMIVO.svg/640px-GAMIVO.svg.png",
    "Green Man Gaming": "https://upload.wikimedia.org/wikipedia/commons/d/d8/Green_Man_Gaming_logo.svg",
    "Instant Gaming" :"https://i.ibb.co/RTNmPbD0/instant-gaming.png",
    "Nuuvem": "https://i.ibb.co/QjpF9HF7/nuuuvem.png",
    "YUPLAY": "https://i.ibb.co/hFS4f5nF/logo-height-30.webp",
    "Cd Keys": "https://i.ibb.co/7xkVw8vM/CDKeys-logo-Colour.png"

}

@app.route('/genre/<genre_name>')
def genre(genre_name):
    # Filtra os jogos com base no gênero selecionado
    filtered_games = []
    
    for game in games:
        genres = game.get("genres")
        if genres is not None:
            genre_list = [g.strip().lower() for g in genres.split(',')]
            if genre_name.lower() in genre_list:
                # ✅ Formata a data dentro do loop
                if isinstance(game["release_date"], str):
                    game["release_date"] = game["release_date"]  # Já é string, mantém
                elif game["release_date"] is not None:
                    game["release_date"] = game["release_date"].strftime("%d/%m/%Y")
                
                filtered_games.append(game)
            else:
                print(f"Jogo '{game['name']}' não corresponde ao gênero '{genre_name}'. Gêneros: {genre_list}")
        else:
            print(f"Jogo '{game['name']}' não tem gêneros definidos.")
    
    # Se não houver jogos para o gênero, pode exibir uma mensagem de erro ou redirecionar
    if not filtered_games:
        return f"Não há jogos para o gênero '{genre_name}'.", 404
    
    # Pega todos os gêneros
    genres = get_genres_from_db()
    
    return render_template('genre.html', games=filtered_games, genre_name=genre_name, genres=genres)




def get_related_games(game_id):
    conn = None
    try:
        conn = get_read_connection()
        if not conn:
            return []

        with conn.cursor() as cursor:
            # Obtém gêneros do jogo atual
            cursor.execute("SELECT genres FROM games WHERE id = %s", (game_id,))
            game_genres = (cursor.fetchone() or [None])[0] or ""
            
            # Query otimizada
            query = """
                WITH game_genres AS (
                    SELECT unnest(string_to_array(%s, ',')) as genre
                )
                SELECT DISTINCT g.id, g.name, g.image,
                       MIN(gp.price) FILTER (WHERE gp.price > 0) as lowest_price
                FROM games g
                LEFT JOIN game_prices gp ON g.id = gp.game_id
                WHERE g.id != %s
                  AND EXISTS (
                      SELECT 1 FROM game_genres gg 
                      WHERE g.genres LIKE '%%' || gg.genre || '%%'
                  )
                GROUP BY g.id, g.name, g.image
                ORDER BY g.popularity DESC
                LIMIT 10
            """
            
            cursor.execute(query, (game_genres, game_id))
            return [{
                "id": row[0],
                "name": row[1],
                "image": row[2],
                "lowest_price": str(row[3]) if row[3] else None
            } for row in cursor.fetchall()]

    except Exception as e:
        app.logger.error(f"Erro ao buscar relacionados para {game_id}: {e}")
        return []
    finally:
        if conn:
            release_connection(conn)



















@app.route('/increase_popularity/<int:game_id>', methods=['POST'])
def increase_popularity_route(game_id):
    user_ip = request.remote_addr  # Obtém o IP do usuário

    # Verifica se o usuário já votou recentemente
    last_vote = session.get(f"last_vote_{game_id}")

    if last_vote:
        last_vote_time = datetime.strptime(last_vote, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_vote_time

        if time_diff < timedelta(seconds=60):  # Tempo mínimo entre votos (60 segundos)
            return jsonify({"error": "Aguarde antes de votar novamente"}), 429  # Código HTTP 429 = Too Many Requests

    # Atualiza o tempo da última votação na sessão
    session[f"last_vote_{game_id}"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Chama a função que aumenta a popularidade
    new_popularity = increase_popularity(game_id)

    if new_popularity is not None:
        return jsonify({"popularity": new_popularity})
    else:
        return jsonify({"error": "Jogo não encontrado"}), 404





@app.route('/featured-game/<int:game_id>')
def featured_game(game_id):
    # Tenta buscar o jogo no cache primeiro
    all_games = get_cached_games()
    featured_game = next((game for game in all_games if game['id'] == game_id), None)

    # Se não encontrar no cache, busca no banco

    if featured_game:
        return jsonify(featured_game)
    else:
        return jsonify({"error": "Jogo não encontrado"}), 404



@app.route('/')
def home():
    page = request.args.get("page", 1, type=int)  # Página atual
    per_page = 15  # Número de jogos por página
    offset = (page - 1) * per_page  

    all_games = get_cached_games()  # ✅ Obtém os jogos do cache
    total_games = len(all_games)  # ✅ Calcula o total de jogos no cache
    total_pages = (total_games + per_page - 1) // per_page  # 🔹 Arredondamento para cima

    # Paginação dos jogos
    paginated_games = all_games[offset : offset + per_page]

    # Buscar os 15 jogos mais populares
    popular_games = sorted(all_games, key=lambda g: g["popularity"], reverse=True)[:15]

    # Buscar os 15 jogos mais baratos (com preço válido)
    cheapest_games = get_cheapest_games()  # ✅ Já retorna a lista correta direto do banco

        # Jogo em destaque (ID fixo 58)
    featured_game = next((game for game in all_games if game['id'] == 70), None)

    genres = get_genres_from_db()  # ✅ Ainda precisa consultar o banco para os gêneros

    return render_template(
        'index.html',
        featured_game=featured_game,  # Jogo em destaque
        games=paginated_games,
        popular_games=popular_games,
        cheapest_games=cheapest_games,
        genres=genres,
        page=page,
        total_pages=total_pages
    )









@app.route('/search')
def search():
    query = request.args.get('query', "").strip().lower()
    
    # Validação para evitar consultas inválidas ou muito longas
    if not query or len(query) > 100:
        return render_template('index.html', games=[], query=query, genres=get_genres_from_db(), page=1, total_pages=1)

    conn = get_read_connection()  # ✅ Usa o pool de leitura
    if not conn:
        return render_template('index.html', games=[], query=query, genres=get_genres_from_db(), page=1, total_pages=1)

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT g.id, g.name, g.image, 
                COALESCE((SELECT MIN(price) FROM game_prices WHERE game_prices.game_id = g.id AND price IS NOT NULL AND price > 0), 0.00) 
                AS lowest_price
                FROM games g
                WHERE LOWER(g.name) ILIKE %s 
                LIMIT 15
            """, (f"%{query}%",))  # Tenta % diretamente

            resultados = cursor.fetchall()

        if not resultados:
            print(f"Nenhum jogo encontrado para '{query}'")

        # Ajusta os resultados para garantir que `lowest_price` sempre exista
        games = [{"id": row[0], "name": row[1], "image": row[2], "lowest_price": row[3]} for row in resultados]

        return render_template('index.html', games=games, query=query, genres=get_genres_from_db(), page=1, total_pages=1)

    except Exception as e:
        print(f"Erro ao buscar jogos: {e}")
        return render_template('index.html', games=[], query=query, genres=get_genres_from_db(), page=1, total_pages=1)

    finally:
        release_connection(conn)  # ✅ Devolve a conexão ao pool (eficiente!)









@app.route('/jogo/<int:game_id>')
def pagina_jogo(game_id):
    jogo = get_game_by_id(game_id)  
    if jogo is None:
        abort(404)

    # Escapando os dados manualmente
    jogo["name"] = escape(jogo["name"])
    jogo["description"] = escape(jogo["description"])

    jogo["lowest_price"] = get_lowest_price(jogo)
    genres = get_genres_from_db()
    related_games = get_related_games(game_id)

    return render_template(
        "jogo.html",
        jogo=jogo,  
        store_icons=store_icons,
        genres=genres,
        related_games=related_games
    )


@app.route('/how-work')
def how_work():
    genres = get_genres_from_db()  # Se quiser exibir os gêneros no menu
    return render_template('how-work.html', genres=genres)


@app.route('/about')
def about():
    genres = get_genres_from_db()  # Se quiser exibir os gêneros no menu
    return render_template('about.html', genres=genres)



@app.template_filter('format_currency')
def format_currency(value):
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return value

