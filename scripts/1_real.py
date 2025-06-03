import time
import requests
import discord
import asyncio
from database import connect

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
        f"APROVEITE ESSA OPORTUNIDADE\n\n"
        f"💥 <b>{game_name}</b> Ainda está barato, aproveite 💥 \n\n"
        f"🔥 Preço Promocional: <b>R${price:.2f}</b> \n\n"
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
        title=f"🔥 {game_name} está com um DESCONTO IMPERDÍVEL, MUITO PRÓXIMO DO MENOR PREÇO HISTÓRICO!",
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
    """Atualiza os menores preços e envia promoções apenas se estiver até R$10 acima do histórico."""
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
            query_lowest_history = "SELECT MIN(price) FROM game_price_history WHERE game_id = %s AND price > 0;"
            cursor.execute(query_lowest_history, (game_id,))
            lowest_price_recorded = cursor.fetchone()[0]

            # Ignora totalmente se não houver histórico
            if lowest_price_recorded is None:
                continue

            # Verifica APENAS se está até R$10 acima do histórico
            if current_lowest_price <= (lowest_price_recorded + 1) and current_lowest_price >= lowest_price_recorded:
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
                    store_url = f"https://www.pixelprice.com.br/jogo/{game_id}"

                    # Envia para Telegram
                    telegram_response = send_telegram_message(game_name, current_lowest_price, store_name, image_url, store_url)
                    
                    if telegram_response.get("ok"):
                        # Envia para Discord
                        channel = client.get_channel(DISCORD_CHANNEL_ID)
                        if channel:
                            await send_discord_promotion(channel, game_name, current_lowest_price, store_name, store_url, image_url)
                        else:
                            print("❌ Erro: Canal do Discord não encontrado.")

                        print(f"✅ Promoção enviada para {game_name} (Preço próximo do histórico)")
                    else:
                        print(f"❌ Falha no Telegram para {game_name}: {telegram_response}")

                    time.sleep(2)  # Mantém o delay entre envios

        print("✅ Atualização concluída!")
    except Exception as e:
        print(f"Erro crítico: {e}")
    finally:
        if conn:
            conn.close()

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
    await update_lowest_prices()

# Iniciar o bot do Discord
client.run(DISCORD_TOKEN)