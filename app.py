from flask import Flask, request, render_template, abort, session, jsonify
from decimal import Decimal
import json
import os
from datetime import datetime, timedelta
from markupsafe import escape
from flask_talisman import Talisman
import re

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Necessário para usar sessões

# Caminho para o arquivo games.json
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'games.json')

def load_games_data():
    """Carrega os dados dos jogos do arquivo JSON."""
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as file:
            data = json.load(file)
            if isinstance(data, dict) and "games" in data:  # Verifica se o JSON é um dicionário com a chave "games"
                return data["games"]  # Retorna a lista de jogos
            else:
                print("Erro: O arquivo JSON não contém a chave 'games'.")
                return []
    except Exception as e:
        print(f"Erro ao carregar dados do arquivo JSON: {e}")
        return []

def save_games_data(data):
    """Salva os dados dos jogos no arquivo JSON."""
    try:
        with open(DATA_PATH, 'w', encoding='utf-8') as file:
            json.dump({"games": data}, file, ensure_ascii=False, indent=4)  # Salva no formato correto
    except Exception as e:
        print(f"Erro ao salvar dados no arquivo JSON: {e}")

def get_genres_from_data(games):
    """Extrai todos os gêneros únicos dos jogos."""
    genres = set()
    for game in games:
        if isinstance(game, dict) and game.get("genres"):  # Verifica se é um dicionário e tem a chave "genres"
            genres.update([g.strip() for g in game["genres"].split(',')])
    return sorted(genres)

def is_valid_url(url):
    """Verifica se a URL é válida."""
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// ou https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domínio
        r'localhost|'  # ou localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ou IP
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ou IP v6
        r'(?::\d+)?'  # Porta opcional
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def get_games_from_data():
    """Retorna todos os jogos com seus preços e links."""
    games_data = load_games_data()
    games = []
    for game in games_data:
        if isinstance(game, dict):  # Verifica se cada item é um dicionário
            game_info = {
                "id": game.get("id"),
                "name": game.get("name", "Nome não disponível"),
                "description": game.get("description", "Descrição não disponível"),
                "genres": game.get("genres"),
                "release_date": game.get("release_date", "Data não disponível"),
                "image": game.get("image", ""),
                "images": game.get("images", []),
                "green_man_nome": game.get("green_man_nome"),
                "popularity": game.get("popularity", 0),
                "links": game.get("links", [])  # Usa os links diretamente do JSON
            }

            # Calcula o menor preço válido
            prices = []
            for link in game_info["links"]:
                if isinstance(link, dict):
                    price = link.get("price")
                    if price is not None and price > 0:  # Verifica se o preço não é None e é maior que 0
                        prices.append(price)

            # Adiciona o menor preço ao jogo
            game_info["lowest_price"] = min(prices) if prices else None

            games.append(game_info)
    return games

def increase_popularity(game_id):
    """Aumenta a popularidade de um jogo."""
    games_data = load_games_data()
    for game in games_data:
        if isinstance(game, dict) and game.get("id") == game_id:
            game["popularity"] = game.get("popularity", 0) + 1
            save_games_data(games_data)
            return game["popularity"]
    return None

def get_game_by_id(game_id):
    """Retorna os detalhes de um jogo específico."""
    games_data = load_games_data()
    for game in games_data:
        if isinstance(game, dict) and game.get("id") == game_id:
            new_popularity = increase_popularity(game_id)
            game_info = {
                "id": game.get("id"),
                "name": game.get("name", "Nome não disponível"),
                "description": game.get("description", "Descrição não disponível"),
                "genres": game.get("genres"),
                "release_date": game.get("release_date", "Data não disponível"),
                "image": game.get("image", ""),
                "images": game.get("images", []),
                "green_man_nome": game.get("green_man_nome"),
                "popularity": new_popularity if new_popularity is not None else game.get("popularity", 0),
                "links": game.get("links", [])  # Usa os links diretamente do JSON
            }
            return game_info
    return None

def get_cheapest_games():
    """Retorna os jogos mais baratos."""
    games = get_games_from_data()
    cheapest_games = [game for game in games if game.get("lowest_price") is not None]
    return sorted(cheapest_games, key=lambda x: x["lowest_price"])[:15]

def get_lowest_price(game):
    """Retorna o menor preço de um jogo."""
    prices = []
    for link in game.get("links", []):
        if isinstance(link, dict):
            price = link.get("price")
            if price is not None and price > 0:  # Verifica se o preço não é None e é maior que 0
                prices.append(price)
    return min(prices) if prices else None

# Ícones das lojas
store_icons = {
    "Steam": "https://i.ibb.co/x8FkBLk7/steam-logo-6.png",
    "GOG": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/GOG.com_logo_no_URL.svg/640px-GOG.com_logo_no_URL.svg.png",
    "Humble Bundle": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Humble_Bundle_H_logo_red.svg/640px-Humble_Bundle_H_logo_red.svg.png",
    "Gamivo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/GAMIVO.svg/640px-GAMIVO.svg.png",
    "Green Man Gaming": "https://upload.wikimedia.org/wikipedia/commons/d/d8/Green_Man_Gaming_logo.svg",
    "Instant Gaming": "https://i.ibb.co/RTNmPbD0/instant-gaming.png",
    "Nuuvem": "https://i.ibb.co/QjpF9HF7/nuuuvem.png",
    "Cd Keys": "https://i.ibb.co/7xkVw8vM/CDKeys-logo-Colour.png"
}

@app.route('/genre/<genre_name>')
def genre(genre_name):
    games = get_games_from_data()
    filtered_games = []
    for game in games:
        if isinstance(game, dict):
            genres = game.get("genres")
            if genres is not None:
                genre_list = [g.strip().lower() for g in genres.split(',')]
                if genre_name.lower() in genre_list:
                    filtered_games.append(game)
    if not filtered_games:
        return f"Não há jogos para o gênero '{genre_name}'.", 404
    genres = get_genres_from_data(games)
    return render_template('genre.html', games=filtered_games, genre_name=genre_name, genres=genres)

@app.route('/increase_popularity/<int:game_id>', methods=['POST'])
def increase_popularity_route(game_id):
    user_ip = request.remote_addr
    last_vote = session.get(f"last_vote_{game_id}")
    if last_vote:
        last_vote_time = datetime.strptime(last_vote, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_vote_time
        if time_diff < timedelta(seconds=60):
            return jsonify({"error": "Aguarde antes de votar novamente"}), 429
    session[f"last_vote_{game_id}"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_popularity = increase_popularity(game_id)
    if new_popularity is not None:
        return jsonify({"popularity": new_popularity})
    else:
        return jsonify({"error": "Jogo não encontrado"}), 404

@app.route('/')
def home():
    page = request.args.get("page", 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page
    games = get_games_from_data()
    total_games = len(games)
    total_pages = (total_games + per_page - 1) // per_page
    all_games = games[offset:offset + per_page]
    popular_games = sorted(games, key=lambda x: x.get("popularity", 0), reverse=True)[:15]
    cheapest_games = get_cheapest_games()
    genres = get_genres_from_data(games)
    return render_template('index.html', games=all_games, popular_games=popular_games, cheapest_games=cheapest_games, genres=genres, page=page, total_pages=total_pages)

@app.route('/search')
def search():
    query = request.args.get('query', "").strip().lower()
    if not query or len(query) > 100:
        return render_template('index.html', games=[], query=query, genres=get_genres_from_data([]), page=1, total_pages=1)
    games = get_games_from_data()
    filtered_games = [game for game in games if isinstance(game, dict) and query in game.get("name", "").lower()]
    return render_template('index.html', games=filtered_games, query=query, genres=get_genres_from_data(games), page=1, total_pages=1)

@app.route('/jogo/<int:game_id>')
def pagina_jogo(game_id):
    jogo = get_game_by_id(game_id)
    if jogo is None:
        abort(404)

    # Escapando os dados manualmente
    jogo["name"] = escape(jogo["name"])
    jogo["description"] = escape(jogo["description"])

    # Verifica se o jogo tem links antes de calcular o menor preço
    if jogo.get("links"):
        jogo["lowest_price"] = get_lowest_price(jogo)
    else:
        jogo["lowest_price"] = None

    genres = get_genres_from_data(get_games_from_data())
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
    genres = get_genres_from_data(get_games_from_data())
    return render_template('how-work.html', genres=genres)

@app.route('/about')
def about():
    genres = get_genres_from_data(get_games_from_data())
    return render_template('about.html', genres=genres)

@app.template_filter('format_currency')
def format_currency(value):
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return value

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, debug=False)