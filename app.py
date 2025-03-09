from flask import Flask, request, render_template, abort, session, jsonify
import os
import psycopg2

def connect():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None
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


# Define o diretório raiz como o local dos templates
app = Flask(__name__, template_folder=os.getcwd())



import re



def get_genres_from_db():
    try:
        conn = connect()
        if not conn:
            print("Erro: Não foi possível conectar ao banco de dados.")
            return []

        with conn.cursor() as cursor:
         query = "SELECT DISTINCT genres FROM games WHERE genres IS NOT NULL"
         cursor.execute(query)
         rows = cursor.fetchall()

        if not rows:
            print("Nenhum gênero encontrado no banco de dados.")
            return []

        genres = set()  # Usamos um set para garantir que os gêneros sejam únicos
        for row in rows:
            genre = row[0]
            if genre:
                # Separar múltiplos gêneros caso estejam concatenados por vírgula
                genres.update([g.strip() for g in genre.split(',')])

        return sorted(genres)  # Retorna uma lista ordenada de gêneros

    except Exception as e:
        print(f"Erro")
        return []

    finally:
        if conn:
            conn.close()




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
    try:
        conn = connect()
        if not conn:
            print("Erro: Não foi possível conectar ao banco de dados.")
            return []

        cursor = conn.cursor()
        query = """
        SELECT 
            g.id, 
            g.name, 
            g.description, 
            g.genres,
            g.release_date, 
            g.image, 
            g.images, 
            g.green_man_nome,
            g.popularity,  -- Adiciona a popularidade,
            gp.store_name, 
            gp.price, 
            gp.url
        FROM 
            games g
        LEFT JOIN 
            game_prices gp 
        ON 
            g.id = gp.game_id
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            print("Nenhum dado encontrado no banco de dados.")
            return []

        games = {}
        for row in rows:
            game_id, name, description, genres, release_date, image, images, green_man_nome, popularity, store_name, price, url = row

            # Verifique se os campos não são None
            name = name if name is not None else "Nome não disponível"
            description = description if description is not None else "Descrição não disponível"
            release_date = release_date if release_date is not None else "Data não disponível"
            image_url = image if image else ""  # Caso a imagem seja None ou vazia

            # Tratando o campo 'images'
            images_list = []
            if images is not None:
                if isinstance(images, str):
                    try:
                        images_list = json.loads(images) if images else []
                    except json.JSONDecodeError:
                        print(f"Erro ao decodificar o campo 'images' para o jogo {game_id}.")
                elif isinstance(images, list):
                    images_list = images
                else:
                    print(f"Campo 'images' mal formatado para o jogo {game_id}.")

            if game_id not in games:
                games[game_id] = {
                    "id": game_id,
                    "name": name,
                    "description": description,
                    "genres": genres,
                    "release_date": release_date,
                    "image": image_url,
                    "images": images_list,
                    "green_man_nome": green_man_nome,
                    "popularity": popularity,
                    "links": []
                }

            # Verificar se store_name, url e preço estão disponíveis antes de adicionar o link
            if store_name and url and is_valid_url(url) and price and price > 0:
                games[game_id]["links"].append({
                    "store": store_name,
                    "price": price,
                    "url": url
                })

        return list(games.values())

    except Exception as e:
        print(f"Erro ao buscar jogos do banco: {e}")
        return []

    finally:
        if conn:
            conn.close()


def increase_popularity(game_id):
    print(f"Aumentando popularidade do jogo ID {game_id}")  # TESTE

    conn = connect()
    if not conn:
        print("Erro: Não foi possível conectar ao banco de dados.")
        return None

    try:
        cursor = conn.cursor()
        query = """
        UPDATE games
        SET popularity = popularity + 1
        WHERE id = %s
        RETURNING popularity;
        """
        
        cursor.execute(query, (game_id,))
        new_popularity = cursor.fetchone()

        if new_popularity:
            conn.commit()  # 🔹 Confirma a transação apenas se tudo der certo
            print(f"Nova popularidade: {new_popularity[0]}")  # TESTE
            return new_popularity[0]
        else:
            print(f"Erro")
            conn.rollback()  # 🔹 Desfaz alterações caso o jogo não seja encontrado
            return None

    except Exception as e:
        conn.rollback()  # 🔹 Evita que a conexão fique travada
        print(f"Erro ao aumentar a popularidade: {e}")
        return None

    finally:
        cursor.close()
        conn.close()







def get_game_by_id(game_id):
    conn = connect()
    if not conn:
        print("Erro: Não foi possível conectar ao banco de dados.")
        return None

    try:
        cursor = conn.cursor()
        
        # Consulta principal para obter os dados do jogo
        query = """
        SELECT id, name, description, genres, release_date, image, images, green_man_nome, popularity, tumb
        FROM games
        WHERE id = %s
        """

        cursor.execute(query, (game_id,))
        game = cursor.fetchone()

        if not game:
            print("Jogo não encontrado.")
            return None

        # Aumenta a popularidade e obtém o novo valor
        new_popularity = increase_popularity(game_id)

        # Ajuste para o campo 'images'
        images = game[6]
        if isinstance(images, str) and images.strip():
            try:
                images = json.loads(images)
            except json.JSONDecodeError:
                print("Erro ao decodificar JSON de 'images'. Definindo como lista vazia.")
                images = []
        elif not images:
            images = []

        # Consulta os preços e URLs das lojas associadas ao jogo
        query_prices = """
        SELECT store_name, price, url FROM game_prices WHERE game_id = %s
        """
        cursor.execute(query_prices, (game_id,))
        prices_data = cursor.fetchall()

        # Filtra apenas lojas que têm preço válido (> 0) e URL não vazia
        store_links = [
            {"store": store, "price": price, "url": url}
            for store, price, url in prices_data
            if price is not None and price > 0 and url and url.strip()
        ]

        # Ordena os links pelo menor preço primeiro
        store_links.sort(key=lambda x: x["price"])

        game_data = {
       "id": game[0],
       "name": game[1],
       "description": game[2],
       "genres": game[3],
       "release_date": str(game[4]),
       "image": game[5],
       "images": images,
       "green_man_nome": game[7],
       "popularity": new_popularity if new_popularity is not None else game[8],
       "tumb": game[9],  # Novo campo adicionado
       "links": store_links
}


        return game_data

    except Exception as e:
        print(f"Erro")
        return None

    finally:
        cursor.close()
        conn.close()





def get_cheapest_games():
    conn = connect()
    if not conn:
        return []

    try:
        with conn.cursor() as cursor:  # ✅ Agora o cursor fecha corretamente
            query = """
                SELECT g.id, g.name, g.image, MIN(p.price) AS lowest_price
                FROM games g
                JOIN game_prices p ON g.id = p.game_id
                WHERE p.price > 0
                GROUP BY g.id, g.name, g.image
                ORDER BY lowest_price ASC
                LIMIT 15;
            """
            cursor.execute(query)
            cheapest_games = cursor.fetchall()
        return cheapest_games
    except Exception as e:
        print(f"Erro ao buscar os jogos mais baratos: {e}")
        return []
    finally:
        conn.close()


# Função para calcular o menor preço
def get_lowest_price(game):
    lowest_price = Decimal('Infinity')  # Valor inicial alto
    lowest_price_str = None

    if "links" in game:
        for link in game["links"]:
            price = link["price"]
            if price is not None:
                try:
                    price_decimal = Decimal(price)  # Converte o preço para Decimal
                    if price_decimal < lowest_price:
                        lowest_price = price_decimal
                        lowest_price_str = str(lowest_price)
                except Exception as e:
                    print(f"Erro ao converter o preço para Decimal: {e}")

    return lowest_price_str




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


game["release_date"] = game["release_date"].strftime("%d/%m/%Y")



def get_related_games(game_id):
    try:
        conn = connect()
        if not conn:
            print("Erro: Não foi possível conectar ao banco de dados.")
            return []

        with conn.cursor() as cursor:
            # Buscar os gêneros do jogo atual
            cursor.execute("SELECT genres FROM games WHERE id = %s", (game_id,))
            game_data = cursor.fetchone()
            if not game_data:
                print(f"Nenhum jogo encontrado com o ID {game_id}")
                return []

            game_genres = game_data[0] or ""
            genre_list = [g.strip() for g in game_genres.split(',') if g.strip()]

            # Se houver gêneros, construímos a query dinamicamente de forma segura
            query_base = sql.SQL("""
                SELECT g.id, g.name, g.description, g.genres, g.release_date, g.image, g.images,
                       g.green_man_nome, g.popularity, gp.store_name, gp.price, gp.url
                FROM games g
                LEFT JOIN game_prices gp ON g.id = gp.game_id
                WHERE g.id != %s
            """)

            params = [game_id]

            if genre_list:
                genre_conditions = sql.SQL(" OR ").join(
                    sql.SQL("g.genres ILIKE %s") for _ in genre_list
                )
                query_base += sql.SQL(" AND (") + genre_conditions + sql.SQL(")")
                params.extend([f"%{genre}%" for genre in genre_list])

            query_base += sql.SQL(" ORDER BY g.popularity DESC")

            # Executa a query com os parâmetros
            cursor.execute(query_base, params)
            rows = cursor.fetchall()

            related_games = {}
            for row in rows:
                (related_id, name, description, genres, release_date, image, images, 
                 green_man_nome, popularity, store_name, price, url) = row

                name = name or "Nome não disponível"
                description = description or "Descrição não disponível"
                release_date = release_date or "Data não disponível"
                image_url = image or ""

                images_list = []
                if images:
                    try:
                        images_list = json.loads(images) if isinstance(images, str) else images
                    except json.JSONDecodeError:
                        print(f"Erro ao decodificar 'images' para o jogo {related_id}")

                if related_id not in related_games:
                    related_games[related_id] = {
                        "id": related_id,
                        "name": name,
                        "description": description,
                        "genres": genres,
                        "release_date": release_date,
                        "image": image_url,
                        "images": images_list,
                        "green_man_nome": green_man_nome,
                        "popularity": popularity,
                        "links": [],
                        "lowest_price": None
                    }

                if store_name and url and is_valid_url(url) and price and price > 0:
                    related_games[related_id]["links"].append({
                        "store": store_name,
                        "price": price,
                        "url": url
                    })

            for game in related_games.values():
                valid_prices = [link["price"] for link in game["links"] if link["price"] > 0]
                game["lowest_price"] = min(valid_prices) if valid_prices else None

            print(f"Jogos relacionados retornados: {len(related_games)}")
            return list(related_games.values())

    except Exception as e:
        print(f"Erro ao buscar jogos relacionados: {e}")
        return []

    finally:
        if conn:
            conn.close()



















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









@app.route('/')
def home():
    page = request.args.get("page", 1, type=int)  # Página atual
    per_page = 15  # Jogos por página
    offset = (page - 1) * per_page  

    conn = connect()
    cur = conn.cursor()

    # Contar total de jogos para a paginação
    cur.execute("SELECT COUNT(*) FROM games")
    total_games = cur.fetchone()[0]
    total_pages = (total_games + per_page - 1) // per_page  # Arredonda para cima

    # Buscar os jogos com menor preço válido (paginação aplicada)
    cur.execute("""
    SELECT g.id, g.name, g.image, COALESCE(
        (SELECT MIN(price) FROM game_prices WHERE game_prices.game_id = g.id AND price IS NOT NULL AND price > 0),
        NULL
    ) AS lowest_price
    FROM games g
    ORDER BY g.id
    LIMIT %s OFFSET %s;
    """, (per_page, offset))


    all_games = [
        {"id": row[0], "name": row[1], "image": row[2], "lowest_price": row[3]}
        for row in cur.fetchall()
    ]

    # Buscar os 15 jogos mais populares com menor preço válido
    cur.execute("""
        SELECT g.id, g.name, g.image, COALESCE(
            (SELECT MIN(price) FROM game_prices WHERE game_prices.game_id = g.id AND price IS NOT NULL AND price > 0),
            NULL
        ) AS lowest_price
        FROM games g ORDER BY g.popularity DESC LIMIT 15;
    """)
    popular_games = [
        {"id": row[0], "name": row[1], "image": row[2], "lowest_price": row[3]}
        for row in cur.fetchall()
    ]

    # Buscar os 15 jogos mais baratos
    cur.execute("""
        SELECT g.id, g.name, g.image, MIN(gp.price) as lowest_price
        FROM games g
        JOIN game_prices gp ON g.id = gp.game_id
        WHERE gp.price IS NOT NULL AND gp.price > 0
        GROUP BY g.id, g.name, g.image
        ORDER BY lowest_price ASC
        LIMIT 15;
    """)
    cheapest_games = [
        {"id": row[0], "name": row[1], "image": row[2], "lowest_price": row[3]}
        for row in cur.fetchall()
    ]

    cur.close()
    conn.close()

    genres = get_genres_from_db()  # Pega os gêneros do banco

    return render_template(
        'index.html',
        games=all_games,
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

    conn = connect()
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
        conn.close()









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



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, debug=True)
