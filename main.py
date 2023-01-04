import keep_alive, os, os.path
from replit import db

os.system('pip install Pillow')

from excepthook import uncaught_exception, install_thread_excepthook
import sys
sys.excepthook = uncaught_exception
install_thread_excepthook()

import boardgen, discord
from discord.ext import commands
from discord.utils import get
import getpass
from PIL import Image, ImageDraw, ImageFont
from io import StringIO, BytesIO
import urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse
import json
import random
import traceback
import html.parser
import pickle
import base64

unescape = html.parser.HTMLParser().unescape


import re
import time
import sqlite3

import requests
from requests.auth import HTTPBasicAuth
from helpers import log, log_exception




imagehost = 'imgur'

guessed = []
board = []
shutdown = False
whose_turn = "None"
num_guesses = 0
board_msg = None

WORD_LIST = [line.rstrip('\n') for line in open('wordlist2.txt')]

QUINTEC = 228267348581154817

DISCORD_KEY = os.getenv("DISCORD_KEY")
#BIN_KEY = base64.b64decode(os.getenv("BIN_KEY")).decode()

team_msg_red = None
team_msg_blue = None
blue = []
red = []
seed = 0

#purl = "https://api.jsonbin.io/b/60d8d2a755b7245a20cfe7b7"

bot = commands.Bot(command_prefix='!')


passphrases = ["[passing]","[pass]"] #stuff that indicates somebody is passing

first_run = True

def write_state():
  global red, blue, guessed, whose_turn, num_guesses, seed, team_msg_red, team_msg_blue
  obj = {}
  obj['red'] = red
  obj['blue'] = blue
  obj['guessed'] = guessed
  obj['turn'] = whose_turn
  obj['num_guesses'] = num_guesses
  obj['seed'] = seed
  db["state"] = obj
  """
  with open('pinr.pkl', 'wb') as output:
    pickle.dump(team_msg_red, output, pickle.HIGHEST_PROTOCOL)
  with open('pinb.pkl', 'wb') as output:
    pickle.dump(team_msg_blue, output, pickle.HIGHEST_PROTOCOL)
  """

def read_state():
  global red, blue, guessed, whose_turn, num_guesses, seed, team_msg_red, team_msg_blue
  if 'state' in db.keys():
    obj = db['state']
    print(obj)
    if 'red' in obj:
      red = obj['red']
    if 'blue' in obj:
      blue = obj['blue']
    if 'guessed' in obj:
      guessed = obj['guessed']
    if 'turn' in obj:
      whose_turn = obj['turn']
    if 'seed' in obj:
      seed = obj['seed']
    if 'num_guesses' in obj:
      num_guesses = obj['num_guesses']
  """
  if os.path.exists('pinr.pkl'):
    with open('pinr.pkl', 'rb') as f:
      team_msg_red = pickle.load(f)
    with open('pinb.pkl', 'rb') as f:
      team_msg_blue = pickle.load(f)
  """
  



 

@bot.event
async def on_ready():
    global first_run
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(name=' Codenames!'))
    if first_run:
        print('Logged in as')
        print(bot.user.name)
        print(bot.user.id)
        print(bot.guilds)
        print('------')
        first_run = False

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send("This command is on a %.2fs cooldown" % error.retry_after)
    else:
        print(("Error: ", error))

@bot.event
async def on_message(message):
    global shutdown, whose_turn, num_guesses, red, blue, hangman_channel, in_hangman, team_msg_red, team_msg_blue

    is_shiro = message.author == bot.user
    is_super_user = True
    is_trusted_user = True

    if message.channel.id == hangman_channel and len(message.content) == 1 and in_hangman:
        await hangman_guess(bot.get_channel(hangman_channel), message.content.lower())

    #print("")
    #print(">> (%s / %s) %s" % (message.author.name, repr(message.user.id), message.content))

    if is_shiro and '**RED**' in message.content:
      if team_msg_red is not None:
        await team_msg_red.unpin()
      team_msg_red = message
      await team_msg_red.pin()
    if is_shiro and '**BLUE**' in message.content:
      if team_msg_blue is not None:
        await team_msg_blue.unpin()
      team_msg_blue = message
      await team_msg_blue.pin()

    clue_pattern = re.compile(r"(?:Red|Blue): [**].+(?:[**])?\s*\((\d+|unlimited|\u221e)\)(?:[**])?", re.IGNORECASE) #Strange things happening with this pattern
    clue_match = re.match(clue_pattern, message.content)

    try:
        print(message.author.name + ": " + message.content)
    except UnicodeEncodeError:
        print(message.author.name + ": " + "<unprintable message>")

    if not is_shiro and clue_match is not None and ((whose_turn == "SMRed" and message.author.mention.replace("!", "") == red[0]) or (whose_turn == "SMBlue" and message.author.mention.replace("!", "") == blue[0])):
        clue = clue_match.groups()[0].strip().lower()
        #print("Matched clue: %s" % (clue))
        if clue.isdigit() and int(clue) > 0:
            num_guesses = int(clue) + 1
        else:
            num_guesses = 100
        toggle_turn()
        write_state()

    #print("num guesses: %s" % (num_guesses))
        
    pat = re.compile(r"\s*[**](.*)[**]\s*", re.IGNORECASE)
    guess_match = re.match(pat, message.content)

    if not is_shiro and guess_match is not None and ((whose_turn == "Red" and message.author.mention.replace("!", "") in red[1:]) or (whose_turn == "Blue" and message.author.mention.replace("!", "") in blue[1:])):
        guess = guess_match.groups()[0].strip().lower()
        if guess.lower().replace("*", "", 6) in passphrases:
            await show_board(message.channel)
            toggle_turn()
            write_state()
        else:
            await process_guess(message.channel, guess.upper().replace("*", "", 6))
            write_state()
    await bot.process_commands(message)

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True)
async def choose(ctx, *args):
  await ctx.send("I picked: " + random.choice(args))

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True, aliases=['guesses', 'who'])
async def status(ctx):
    """Gets the current status of the game."""
    global shutdown, whose_turn, num_guesses, red, blue
    if whose_turn == "Red" or whose_turn == "Blue":
        await ctx.send("%s currently has %s guesses remaining." % (whose_turn, num_guesses if num_guesses < 25 else "unlimited"))
    elif whose_turn[:2] == "SM":
        await ctx.send("We are currently waiting for a clue from the %s spymaster." % (whose_turn[2:]))

async def process_guess(ctx, guess):
    global whose_turn, num_guesses, guessed, board
    condolences = ["Oh, dear.\n", "That's too bad.\n", "I feel for you.\n", "What were you thinking?\n", "Uh... what?\n", "Maybe you'll do better next time.\n", "Seriously?\n", "I hope you feel okay about that.\n", "When will you learn?\n"]
    print(guessed)
    print(board[1])
    if guess in board[1] and not guess.lower() in guessed:
        guessed.append(guess.lower())
        message = guess
        new_turn = False
        game_over = False
        guess_color = board[2][board[1].index(guess)]
        if guess_color == "#3eb2e0":
            message += " is Blue\n"
            if whose_turn == "Red":
                new_turn = True
                message += random.choice(condolences)
            elif whose_turn == "Blue":
                num_guesses -= 1
                if num_guesses == 0:
                    message += "You are out of guesses. "
                    new_turn = True
        elif guess_color == "#dd6664":
            message += " is Red\n"
            if whose_turn == "Blue":
                new_turn = True
                message += random.choice(condolences)
            elif whose_turn == "Red":
                num_guesses -= 1
                if num_guesses == 0:
                    message += "You are out of guesses. "
                    new_turn = True
        elif guess_color == "#f0e766":
            message += " is Yellow (neutral)\n"
            new_turn = True
        elif guess_color == "#808080":
            message += " is Black (assassin!).\nGame over. "
            if whose_turn == "Blue":
                message += "Red wins!"
            elif whose_turn == "Red":
                message += "Blue wins!"
            game_over = True
        
        if new_turn:
            if whose_turn == "Blue":
                message += "It is now Red's turn"
            elif whose_turn == "Red":
                message += "It is now Blue's turn"
            toggle_turn()
            
        await ctx.send(message)
        if new_turn:
            await show_board(ctx)
        if game_over:
            await show_final(ctx)
    elif guess in board[1]:
        await ctx.send("This has already been guessed.")
    else:
        await ctx.send("%s doesn't appear to be on the board..." % (guess.upper()))

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True)
async def flipcoin(ctx):
    """Picks between Red and Blue."""
    await ctx.send(random.choice(["Red", "Blue"]))

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True, aliases=['pingable'])
async def pingme(ctx):
  """Toggles the Codenamer role for pings."""
  role = get(ctx.guild.roles, name='Codenamer')
  if role:
    if 'Codenamer' in map(str, ctx.author.roles):
      await ctx.author.remove_roles(role)
      await ctx.send(":white_check_mark: Role removed.")
    else:
      await ctx.author.add_roles(role)
      await ctx.send(":white_check_mark: Role added.")

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True)
async def blame(ctx):
    """Blames somebody for the horrible state of the current game."""
    await ctx.send("It's %s's fault." % (random.choice(red + blue + ['<@!430070724431183893>', '<@!263796186815791104>'])))

def change_host(msg):
    global imagehost

    pieces = msg.lower().split()
    if len(pieces) >= 2:
        new_host = pieces[1].strip()
        if new_host in ['imgur', 'puush']: imagehost = new_host

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True, aliases=['about', 'rules'])
async def info(ctx):
    embed = discord.Embed(title="Hello! I'm Shiro!", description="I'm a bot to help with the game Codenames. See [here](https://gist.github.com/superplane39/89bd60c159eec0ab7bc897bc78f6802c#file-codenamesrules-md) for the rules and type !help for a list of commands. Have fun!", color=0x00ff00)
    await ctx.send(None, embed=embed)

@bot.command(pass_context=True)
@commands.cooldown(1, 5, commands.BucketType.default)
async def newgame(ctx, *msg):
    """Starts a new game. Make sure to mention all users that are playing. Spymasters are the first two mentions."""
    global red, blue, whose_turn, board, guessed, seed, board
    players = None

    print(ctx.args)
    print(ctx.message.mentions)

    try:
        players = [x.strip().replace("!", "") for x in ctx.args[1:]]
    except Exception as e:
        return

    red = []
    blue = []
    guessed = []

    log('info', 'New game is starting!')
    log('debug', "players: {}".format(players))
    if players is not None and len(players) >= 2:
        spymasters = players[:2]
        random.shuffle(spymasters)

        red = [spymasters[0]]
        blue = [spymasters[1]]

        players = players[2:]
        n = len(players) // 2
        for x in range(n):
            who = random.randrange(len(players))
            red.append(players.pop(who))
        for x in range(n):
            who = random.randrange(len(players))
            blue.append(players.pop(who))

        if players:
            if random.randrange(2):
                red.append(players[0])
            else:
                blue.append(players[0])

        await ctx.send("**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
        await ctx.send("**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))
        time.sleep(2)

    seed = str(random.randint(1, 1000000000))


    for member in ctx.message.mentions:
        print(member.mention)
        if member.mention.replace("!", "") in spymasters:
            print("fpund spymaster")
            await member.create_dm()
            await member.dm_channel.send("https://kodenames-d6aa5.firebaseapp.com/")
            await member.dm_channel.send("Seed: " + str(seed))

    init(seed)
    if board[0]=="#3eb2e0":
        await ctx.send("BLUE goes first!")
        whose_turn = "SMBlue"
    elif board[0]=="#dd6664":
        await ctx.send("RED goes first!")
        whose_turn = "SMRed"
    write_state()
    await show_board(ctx)

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True, aliases=['joinred', 'joinblue'])
async def join(ctx):
    """Joins the current game."""
    await add_user(ctx, ctx.message.content, ctx.author.mention.replace("!", ""))
    write_state()

@bot.command(pass_context=True)
async def leave(ctx):
    """Leaves the current game."""
    await remove_user(ctx, ctx.message.content, ctx.author.mention.replace("!", ""))
    write_state()

async def add_user(ctx, content, name):
    global red, blue

    if not red or not blue:
        await ctx.send("Sorry, I don't have any teams stored right now!")
        return

    segments = content.strip().split(None, 1)
    if len(segments) == 1:
        joining_user = name
    else:
        joining_user = unescape(segments[1]).strip()

    dest_color = ''
    if content.lower().strip().startswith("!joinred"):
        dest_color = 'red'
    elif content.lower().strip().startswith("!joinblue"):
        dest_color = 'blue'
    else:
        if len(red) != len(blue):
            dest_color = 'red' if len(red) < len(blue) else 'blue'
        else:
            dest_color = random.choice(['red', 'blue'])
        await ctx.send("Hi %s, you'll be joining team %s!" % (joining_user, dest_color))

    if dest_color == 'red':
        red.append(joining_user)
        await ctx.send("**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
    else:
        blue.append(joining_user)
        await ctx.send("**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))

async def remove_user(ctx, content, name):
    global red, blue

    if not red or not blue:
        await ctx.send("Sorry, I don't have any teams stored right now!")
        return

    segments = content.strip().split(None, 1)
    if len(segments) == 1:
        leaving_user = name
    else:
        leaving_user = unescape(segments[1]).strip()

    if leaving_user in red[1:]:
        red.reverse()
        red.remove(leaving_user)
        red.reverse()
        await ctx.send("**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
    if leaving_user in blue[1:]:
        blue.reverse()
        blue.remove(leaving_user)
        blue.reverse()
        await ctx.send("**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))

def init(_seed):
    global seed, guessed, board
    seed = _seed
    board = get_board(seed)


@bot.command(pass_context=True)
@commands.cooldown(1, 10, commands.BucketType.default)
async def board(ctx):
    """Shows the board."""
    await show_board(ctx)

async def show_board(ctx):
    global guessed, seed, board_msg
    solved = []
    for idx, x in enumerate(board[1]):
        if x.lower().strip() in guessed:
            solved.append(idx)
    draw_grid(seed, solved)
    time.sleep(3)
    """
    url = upload_image(im)
    urllib.request.urlretrieve(url, "board.jpg")
    """
    if board_msg is not None:
      await board_msg.unpin()
    board_msg = await ctx.send(file=discord.File("board.jpg"))
    await board_msg.pin()

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True)
async def finalboard(ctx):
  """Shows the final board with all colors filled in."""
  await show_final(ctx)

async def show_final(ctx):
    global guessed, board, whose_turn, num_guesses, red, blue, team_msg_red, team_msg_blue
    solved = list(range(25))
    '''Past code, in case this doesn't work for some reason:
    solved = []
    for idx, x in enumerate(board[1]):
        solved.append(idx)
        '''
    draw_grid(seed, solved)
    time.sleep(3)
    """
    url = upload_image(im)
    urllib.request.urlretrieve(url, "board.jpg")
    """
    guessed = []
    board = []
    red = []
    blue = []
    whose_turn = "None"
    num_guesses = 0
    await ctx.send(file=discord.File("board.jpg"))
    if board_msg is not None:
      await board_msg.unpin()
      board_msg = None
    await team_msg_red.unpin()
    await team_msg_blue.unpin()
    team_msg_red = None
    team_msg_blue = None
    write_state()

def get_board(seed):
    board = boardgen.createNewGame(seed).split(',')
    return board[0], board[1:26], board[26:51]

def draw_grid(seed, solved):
    WIDTH = 500
    GRID_TOTAL_WIDTH = 500
    GRID_WIDTH = GRID_TOTAL_WIDTH // 5
    HEIGHT = 330
    GRID_TOTAL_HEIGHT = 300
    GRID_HEIGHT = GRID_TOTAL_HEIGHT // 5

    y_offset = HEIGHT - GRID_TOTAL_HEIGHT

    font = ImageFont.truetype("arial-black.ttf", 12)
    lfont = ImageFont.truetype("arial-black.ttf", 16)
    image1 = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255) )
    draw = ImageDraw.Draw(image1)
    
    blues = 0 #number of blues guessed
    reds = 0  #number of reds guessed
    #print board
    for x in range(5):
        for y in range(5):
            if x*5+y in solved:
                #print 'color: ', board[2][x*5+y]
                draw.rectangle([x*GRID_WIDTH, y_offset + y*GRID_HEIGHT, (x+1)*GRID_WIDTH, y_offset + (y+1)*GRID_HEIGHT], fill=board[2][x*5+y])
                if board[2][x*5+y]=="#3eb2e0":
                    blues+=1
                if board[2][x*5+y]=="#dd6664":
                    reds+=1
    
    bluesremaining = 8-blues
    redsremaining = 8-reds
    if board[0] == "#3eb2e0":
        bluesremaining += 1
    else:
        redsremaining += 1
    #I'm not 100% confident with the draw tools so somebody else can do them if they want

    for x in range(GRID_WIDTH, WIDTH, GRID_WIDTH):
        draw.line([x, y_offset, x, HEIGHT], (0,0,0))
    for y in range(0, HEIGHT, GRID_HEIGHT):
        draw.line([0, y + y_offset, GRID_TOTAL_WIDTH, y + y_offset], (0,0,0))

    for x in range(5):
        for y in range(5):
            word = board[1][x*5+y]

            size = draw.textsize(word, font=font)
            draw.text((x * GRID_WIDTH + GRID_WIDTH/2 - size[0]/2, y_offset + y * GRID_HEIGHT + GRID_HEIGHT/2 - size[1]/2), word, (0,0,0), font=font)

    draw.text((70,1), "RED: %s remaining" % redsremaining, (255,0,0), font=lfont)
    draw.text((270,1), "BLUE: %s remaining" % bluesremaining, (0,0,255), font=lfont)
    
    image1.save("board.jpg")
    """
    output = BytesIO()
    image1.save(output, format='png')
    
    return output.getvalue()
    """
"""
def pin_red(msg):
    global pinned_message_red
    if pinned_message_red is not None:
        try:
            pinned_message_red._client._br.edit_message(pinned_message_red.id, "**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
            return
        except:
            pinned_message_red.cancel_stars()
    msg.pin()
    pinned_message_red = msg

def pin_blue(msg):
    global pinned_message_blue
    if pinned_message_blue is not None:
        try:
            pinned_message_blue._client._br.edit_message(pinned_message_blue.id, "**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))
            return
        except:
            pinned_message_blue.cancel_stars()
    msg.pin()
    pinned_message_blue = msg
"""

def upload_image(im):
    """
    if imagehost == 'puush':
        try:
            return upload_puush(im)
        except:
            pass
    return upload_imgur(im)
    """

def upload_imgur(im):
    data = urllib.parse.urlencode([('image', im)]).encode("utf-8")
    req = urllib.request.Request('https://api.imgur.com/3/image', data=data, headers={"Authorization": "Client-ID 44c2dcd61ab0bb9"})
    return json.loads(urllib.request.urlopen(req).read())["data"]["link"]

"""
#DISABLED
def upload_puush(im):
    im = StringIO(im)
    im.name = 'temp.png'
    account = puush.Account(Puush_API_Key)
    f = account.upload(im)
    return f.url

#DISABLED
def submit_secret(secret):
    data = {'secret': secret}
    r = requests.post('https://onetimesecret.com/api/v1/share', data=data, auth=HTTPBasicAuth(OTS_User, OTS_Password))
    return 'https://onetimesecret.com/secret/' + r.json()['secret_key']
"""

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True)
async def teams(ctx):
    """Shows the current teams."""
    global red,blue
    await ctx.send("**RED team**: *%s*, %s" % (red[0], ', '.join(red[1:])))
    await ctx.send("**BLUE team**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True)
async def redteam(ctx):
  """Pings the red team guessers."""
  global red
  await ctx.send(', '.join(red[1:]))

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True)
async def blueteam(ctx):
  """Pings the blue team guessers."""
  global blue
  await ctx.send(', '.join(blue[1:]))

def toggle_turn():
    global whose_turn
    if whose_turn == "Blue":
        whose_turn = "SMRed"
        num_guesses = 0
    elif whose_turn == "SMRed":
        whose_turn = "Red"
    elif whose_turn == "Red":
        whose_turn = "SMBlue"
        num_guesses = 0
    elif whose_turn == "SMBlue":
        whose_turn = "Blue"


hangman_word = []
hangman_status = []
in_hangman = False
hangman_wrong = []
hangman_stage = 4#From 4 to 10
hangman_channel = 0


def get_hangman_word():
    global hangman_status, hangman_word
    ans = "`"
    for i in range(len(hangman_word)):
        if hangman_status[i]:
            ans += hangman_word[i] + " "
        else:
            ans += "_ "
    ans = ans[0:-1]
    ans += "`"
    return ans


def get_word():
    word = ""
    while len(word) < 5 or len(word) > 15:
        word = random.choice(WORD_LIST)
    return word

async def hangman_guess(ctx, letter):
    global hangman_word, hangman_status, in_hangman, hangman_wrong, hangman_stage
    guess = letter.lower()
    if guess in hangman_word:
        for i in range(len(hangman_word)):
            if hangman_word[i] == guess:
                hangman_status[i] = True
    elif guess not in hangman_wrong:
        hangman_wrong.append(guess)
        hangman_stage += 1
    if hangman_stage >= 10:
        await bot.get_channel(783738937080283236).send("**You have been hanged!**")
        await bot.get_channel(783738937080283236).send(file=discord.File('10.jpg'))
        hangman_status = [True] * len(hangman_word)
        await bot.get_channel(783738937080283236).send("The word was " + get_hangman_word())
        in_hangman = False
    elif all(hangman_status):
        await bot.get_channel(783738937080283236).send(":white_check_mark: Congratulations, you have won! The word was " + get_hangman_word())
        in_hangman = False
    else:
        await bot.get_channel(783738937080283236).send(file=discord.File(str(hangman_stage) + ".jpg"))
        if len(hangman_wrong) > 0:
            await bot.get_channel(783738937080283236).send("Incorrect Guesses: " + ', '.join(hangman_wrong))
        await bot.get_channel(783738937080283236).send(get_hangman_word())

@commands.cooldown(1, 3, commands.BucketType.user)
@bot.command(pass_context=True)
async def hangman(ctx, com: str, letter=""):
    """
    Hangman game.
    Usage:
    !hangman start: Starts a new game.
    !hangman guess [letter/word]: Guesses [letter/word] for the current hangman.
    You can also guess by sending single letters in chat.
    """
    global hangman_word, hangman_status, in_hangman, hangman_wrong, hangman_stage, hangman_channel
    if com == 'start':
        if not in_hangman:
            hangman_word = list(get_word())
            if letter != "":
              hangman_word = letter
            hangman_status = [False] * len(hangman_word)
            in_hangman = True
            hangman_wrong = []
            hangman_stage = 4
            hangman_channel = 783738937080283236
            await bot.get_channel(783738937080283236).send(file=discord.File('4.jpg'))
            await bot.get_channel(783738937080283236).send(get_hangman_word())
        else:
            await ctx.send("A hangman game is already currently happening.")
    elif com == 'guess' and in_hangman:
        if len(letter) == 1:
            await hangman_guess(ctx, letter)
        elif len(letter) > 1:
            guess = letter.lower()
            if ''.join(hangman_word) == guess.lower():
                hangman_status = [True] * len(hangman_word)
                await bot.get_channel(783738937080283236).send(":white_check_mark: Correct! The word was " + get_hangman_word())
                in_hangman = False
            else:
                await bot.get_channel(783738937080283236).send(":x: The word is not **" + guess.lower() + "**")
                hangman_stage += 1

read_state() 
init(str(seed))
keep_alive.keep_alive()
bot.run(DISCORD_KEY)

