import os
import json
from database import connect

def fetch_all_data():
    conn = connect()
    if not conn:
        print("Erro: Não foi possível conectar ao banco de dados.")
        return

    try:
        cursor = conn.cursor()

        # Query para buscar informações das tabelas 'games' e 'game_prices'
        query = """
        SELECT g.id, g.name, g.description, g.genres, g.release_date, g.image, g.images, 
               g.tumb, g.green_man_nome, g.nuuvem_id, g.popularity, 
               gp.store_name, gp.price, gp.url
        FROM games g
        LEFT JOIN game_prices gp ON g.id = gp.game_id
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        games = {}

        for row in rows:
            game_id, name, description, genres, release_date, image, images, tumb, green_man_nome, nuuvem_id, popularity, store_name, price, url = row
            
            if game_id not in games:
                games[game_id] = {
                    "id": game_id,
                    "name": name,
                    "description": description,
                    "genres": genres,
                    "release_date": str(release_date),
                    "image": image,
                    "images": images if images else [],
                    "tumb": tumb,  # Adicionando a coluna tumb
                    "green_man_nome": green_man_nome,
                    "nuuvem_id": nuuvem_id,
                    "popularity": popularity,
                    "lowest_recorded_price": None,  
                    "links": []
                }
            
            if store_name:
                games[game_id]["links"].append({
                    "store": store_name,
                    "price": float(price) if price else None,
                    "url": url
                })

        # Buscar o menor preço registrado na tabela game_price_history
        history_query = """
        SELECT game_id, MIN(price) 
        FROM game_price_history 
        WHERE price > 0  
        GROUP BY game_id;
        """
        cursor.execute(history_query)
        history_data = cursor.fetchall()

        for game_id, lowest_price in history_data:
            if game_id in games:
                games[game_id]["lowest_recorded_price"] = float(lowest_price)

        # Criar o dicionário final sem os dados da Instant Gaming
        result = {
            "total_games": len(games),
            "games": list(games.values())
        }

        # Criar diretório 'data' se não existir
        os.makedirs("data", exist_ok=True)

        # Salvar JSON minificado para melhor desempenho
        with open("data/games.json", "w", encoding="utf-8") as json_file:
            json.dump(result, json_file, separators=(",", ":"), ensure_ascii=False)

        print("Dados exportados para 'data/games.json'.")
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fetch_all_data()
