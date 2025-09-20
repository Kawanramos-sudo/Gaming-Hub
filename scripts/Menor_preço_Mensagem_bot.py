import time
import requests
import discord
import asyncio
from database import connect

import os

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
DISCORD_TOKEN = os.environ['DISCORD_TOKEN']
DISCORD_CHANNEL_ID = int(os.environ['DISCORD_CHANNEL_ID'])


# Configuração do bot do Discord
discord_intents = discord.Intents.default()
discord_intents.messages = True
client = discord.Client(intents=discord_intents)

def send_telegram_message(game_name, price, store_name, image_url, store_url):
    """Envia a promoção para o Telegram e trata erros com logs detalhados."""
    message = (
        f"💥 <b>{game_name}</b> está com um DESCONTO IMPERDÍVEL! 💥 \n\n"
        f"🔥 Preço Promocional: <b>R${price:.2f}</b> \n\n"
        f"<b>⚡ Válido por tempo LIMITADO!⏳</b>\n\n"
        f"💬 Quer mais descontos EXCLUSIVOS?\n"
        f"👉 Faça parte do nosso canal AGORA: <a href='https://t.me/pixelpricesales'>Clique aqui!</a>\n"
        f"🎮 Entre no nosso Discord e participe da comunidade!: <a href='https://discord.gg/SzFDtPQFxj'>Junte-se aqui!</a>\n\n"
        f"🔗 LINK para garantir o seu 👇:\n<a href='{store_url}'>Comprar agora!</a>"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": message,
        "parse_mode": "HTML",  # Usando HTML para formatação segura
        "photo": image_url
    }
    
    response = requests.post(url, data=data)
    return response.json()

async def send_discord_promotion(channel, game_name, price, store_name, store_url, image_url):
    """Envia a promoção para o Discord."""
    embed = discord.Embed(
        title=f"🔥 {game_name} em promoção!",
        description=(
            f"💥 Preço Promocional: **R${price:.2f}**\n"
            f"🛒 Loja: **{store_name}**\n"
            f"🔗 [Comprar agora]({store_url})\n\n"
            f"🎮 Quer mais promoções? Junte-se ao nosso [Telegram](https://t.me/pixelpricesales) e [Discord](https://discord.gg/SzFDtPQFxj)"
        ),
        color=discord.Color.green()
    )
    embed.set_image(url=image_url)
    await channel.send(embed=embed)
    print(f"✅ Promoção enviada para '{game_name}' no Discord!")

async def update_lowest_prices():
    print("⏳ Iniciando busca por promoções...")
    """Atualiza os menores preços e envia promoções para Telegram e Discord."""
    conn = connect()
    if not conn:
        print("Erro: Não foi possível conectar ao banco de dados.")
        return

    try:
        cursor = conn.cursor()

        # Buscar os menores preços atuais
        query_current_prices = """
        SELECT gp.game_id, MIN(gp.price) AS current_lowest_price
        FROM game_prices gp
        INNER JOIN games g ON gp.game_id = g.id
        WHERE gp.price IS NOT NULL AND gp.price > 0
        GROUP BY gp.game_id;
        """
        cursor.execute(query_current_prices)
        current_prices = cursor.fetchall()

        for game_id, current_lowest_price in current_prices:
            print(f"🔍 Verificando jogo ID: {game_id} | Preço atual: R${current_lowest_price:.2f}")
            query_lowest_history = "SELECT MIN(price) FROM game_price_history WHERE game_id = %s AND price > 0;"
            cursor.execute(query_lowest_history, (game_id,))
            lowest_price_recorded = cursor.fetchone()[0]

            if lowest_price_recorded is None or current_lowest_price < lowest_price_recorded:
                query_game_info = """
                SELECT g.id, g.name, g.image, gp.store_name
                FROM game_prices gp
                INNER JOIN games g ON gp.game_id = g.id
                WHERE gp.game_id = %s AND gp.price = %s
                LIMIT 1;
                """
                cursor.execute(query_game_info, (game_id, current_lowest_price))
                game_info = cursor.fetchone()

                if game_info:
                    game_id, game_name, image_url, store_name = game_info

                    # Construir o novo link para o jogo no seu site
                    store_url = f"https://www.pixelprice.com.br/jogo/{game_id}"

                    # Enviar para o Telegram
                    telegram_response = send_telegram_message(game_name, current_lowest_price, store_name, image_url, store_url)
                    
                    if telegram_response.get("ok"):  # Só registra no banco se a mensagem for enviada com sucesso
                        print(f"✅ Telegram: Mensagem enviada para '{game_name}'")
                        # Enviar para o Discord
                        channel = client.get_channel(DISCORD_CHANNEL_ID)
                        if channel:
                            await send_discord_promotion(channel, game_name, current_lowest_price, store_name, store_url, image_url)
                        else:
                            print("❌ Erro: Não foi possível acessar o canal do Discord.")

                        # Registrar no banco de dados
                        insert_query = """
                        INSERT INTO game_price_history (game_id, store_name, price, recorded_at)
                        VALUES (%s, %s, %s, NOW());
                        """
                        cursor.execute(insert_query, (game_id, store_name, current_lowest_price))
                        conn.commit()
                        print(f"✅ Promoção enviada e registrada para {game_name}! ({store_url})")
                    else:
                        error_code = telegram_response.get("error_code")
                        if error_code == 429:  # Too Many Requests
                            retry_after = telegram_response.get("parameters", {}).get("retry_after", 10)
                            print(f"⏳ Erro 429: Esperando {retry_after} segundos antes de tentar novamente...")
                            time.sleep(retry_after)
                        else:
                            print(f"❌ Erro ao enviar {game_name} para o Telegram: {telegram_response}")

                time.sleep(2)  # Pequeno delay entre envios para evitar bloqueios

        print("✅ Atualização concluída!")
    except Exception as e:
        print(f"Erro ao atualizar os menores preços: {e}")
    finally:
        if conn:
            conn.close()


@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
    try:
        await update_lowest_prices()
        print("✅ Todas as promoções processadas!")
    except Exception as e:
        print(f"❌ Erro durante o processamento: {e}")
    finally:
        # Desconecta o bot após finalizar
        await client.close()
        print("✅ Bot desconectado com sucesso!")

# Iniciar o bot do Discord
try:
    client.run(DISCORD_TOKEN)
except Exception as e:
    print(f"❌ Erro ao iniciar o bot: {e}")