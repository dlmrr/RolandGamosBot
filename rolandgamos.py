import requests
import jmespath
import random
import json
import time
import re
import sys
from PIL import Image
import io 
import boto3
from os import environ
from requests_oauthlib import OAuth1

#discogs api_keys
secrets = environ["secrets]

#twitter api keys
API_KEY = environ["API_KEY"]
API_SECRET = environ["API_SECRET"]
ACCESS_TOKEN = environ["ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = environ["ACCESS_TOKEN_SECRET"]
base_url = 'https://api.twitter.com/1.1/'
auth = OAuth1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

    
def load_data():
 	#je charge mon ficher json qui contient les données sur les parties, les rappeurs déjà citéss au cours de la partie et les rappeurs à sélectionner
    global s3
    s3 = boto3.resource('s3')
    obj = s3.Object(bucket_name='rolandgamos', key='roland_gamos.json')
    response = obj.get()
    r = response['Body'].read()
    global tracking_file
    tracking_file = json.loads(r)
    
    #liste des rappeurs déjà cités au cours de la partie en cours
    last_rappeur = tracking_file["manches"][-1]["rappeurs"][-1]
    
    #vérifier qu'il y a bien une partie en cours et sinon la créer
    if (last_rappeur == 'None') or (last_rappeur == None):
        tracking_file["manches"][-1]["rappeurs"].append({"rappeurs" : []})
    
    #si la partie n'a pas encore commencer, noter la data de début
    if "begining_date" not in tracking_file["manches"][-1]:
        print("no begining date")
        if str(tracking_file["manches"][-2]["rappeurs"][-1]) == "None":
            print("adding begin date")
            tracking_file["manches"][-1]["begining_date"] = str(time.time())
        
        #sinon, aller à la partie précédente
        else : 
            print("back to unfinished business")
            tracking_file["manches"][-1] = tracking_file["manches"][-2]

    # si il n'y en a pas, initier une liste de rappeurs et en chosir un au hasar pour commencer la partie
    if ("rappeurs" not in tracking_file["manches"][-1]) or (len(tracking_file["manches"][-1]["rappeurs"]) == 0):
        print("choosing new rapper")
        
        next_rappeur = random.choice(([i[1]["id"] for i in tracking_file["rappeurs_select"].items()]))

        tracking_file["manches"][-1]["rappeurs"] = [next_rappeur]
    #on va utiliser cette liste pour vérifier que des rappeurs n'ont pas déjà été cités
    global liste_rappeur_cités
    liste_rappeur_cités = tracking_file["manches"][-1]["rappeurs"]
    


    
#fonction qui fait un appel à l'api de Discogs et se met en pose si jamais la requête est invalide pour réésayer plus tard
def wait_request(url):
    code = 429
    print("we are now in the request function")
    print(url)
    tries = 0
    
    while code != 200 and tries < 3:
        
        response = requests.get(url)
        code = response.status_code
        if code != 200:
            print(code)
            print("bad request, sleep")
            tries +=1
            time.sleep(61)
            if tries > 3:
                
                
                sys.exit("Too many request failures, stopping execution")
            
    return response
    
#récupérer les sorties d'un artistes
def get_artist_releases(artist_id, full=False):
    print("we are now in the get_artist_releases function")
    base_release = "https://api.discogs.com/artists/{}/releases?" + secrets
    
    releases = []
    
    first_page = wait_request(base_release.format(artist_id))
    nb_pages = first_page.json()["pagination"]["pages"]
    print(nb_pages)
    
    releases += first_page.json()["releases"]
    #si c'est spécifié récupérer la totalité des sorties au lieu de juste la première page de résulats
    if full:

        for page in range(2,nb_pages +1):
            url = base_release.format(artist_id) + "&page={}".format(page)
            n_page = wait_request(url)
            page = n_page.json()["releases"]
            releases += page
    
    
    #certaines urls ne sont pas correctes, il faut les transformer
    url = 'https://api.discogs.com/releases/'
    for ix,i in enumerate(releases):
        if "main_release" in i:
            new_url = url + str(i["main_release"])
            releases[ix]["resource_url"] = new_url

        
    return releases


# on vérifie qu'un album est bien un album de rap français
def check_rap_album(album_base):
    print("we are now in the check_rap_album function")
    
        
    url = album_base + "?" + secrets
    print(url)
    print("making the album request")
    album = wait_request(url)
    album_infos = album.json()
    if ("genres" in album_infos) and ("country" in album_infos):
        genres= album_infos["genres"]
        country = album_infos["country"]
    else:
        return False
    
    if (country == "France") and ("Hip Hop" in genres):
        israp = True
    else:
        israp = False
    return israp
        
    
    

#on vérifie qu'un artiste est bien un rapeur français en vérifiant si ses albums sont des albums de rap
def check_rapper(releases):
    print("we are now in the check-rapper function")
    nb_false = 0
    israp = False
    
    #d'abords les sorties par l'artiste lui même
    mains = jmespath.search("[?role == 'Main'].resource_url",releases)
    
    if len(mains) > 0:
        
        for album in mains:
            
            israp = check_rap_album(album)
            if israp:
                break
                
            else:
                nb_false +=1
                if (nb_false > 1) or (nb_false == len(mains)): #si au moins deux albums ne sont pas du rap, cet artiste n'est pas un rappeur
                    israp = False
                    break
    #si on ne trouve pas de sorties principales, on regarde ses featuring et on répète la même chose
    else:
        appeareances = jmespath.search("[?role == 'Appearance'].resource_url",releases)
        
        if len(appeareances) > 0:
            
            for album in appeareances:

                israp = check_rap_album(album)
                if israp:
                    break
                    
                else:
                    nb_false +=1
                    if (nb_false > 1) or (nb_false == len(appeareances)):
                        israp = False
                        break
    print(f"Rappeur checked : {israp}")
    return israp
                        
# récupérer toutes les infos d'un album
def get_album_infos(album_url):
    print("we are now in the get_album_infos function")
    url = album_url + "?" + secrets
    print(url)
    response = wait_request(url)
    
    album_infos = response.json()
    album_infos = json.loads(json.dumps(album_infos),parse_int=str)
    print("album infos gotten")
    print(album_infos["uri"])
    return album_infos

#on regarde dans un album principal d'un artiste s'il contient des featuring avec des rappeurs qui n'ont pas déjà été cités
def get_main_featuring(album_url):
    print("we are now in the get_main_featuring function")
    album_infos = get_album_infos(album_url)
    

    
    feat_ids = jmespath.search("tracklist[?extraartists][].extraartists[?role == 'Featuring'][].id",album_infos)
    print(feat_ids)
    feat_json = None
    if feat_ids != None:
        for feat in feat_ids:
            
            if feat in liste_rappeur_cités:
                print("on l'a déjà dit")
                return None
            else:
                print(feat)
                print("on ne l'a pas déjà dit")
                print(liste_rappeur_cités)
            releases = get_artist_releases(feat)
            if check_rapper(releases):
                feat_json = (album_infos,feat)
                break
    return feat_json 

#on fait pareil pour les sorties où l'artiste apparait :
def get_appearance_featuring(album_url,artist_id):
    print("we are now in the get_appearance_featuring function")
    album_infos = get_album_infos(album_url)
    
    
    #on vérifie que l'artiste fait bien un featuring sur cette sortie, si oui on récupère les artistes avec qui il collabore
    feat_tracks = jmespath.search("tracklist[?extraartists[?role == 'Featuring' && id == '{}']][]".format(artist_id),album_infos)
    print("feat_tracks : ",feat_tracks)
    if (feat_tracks == None) or (feat_tracks == []):
        return None
    
    feat_artists = jmespath.search("[].artists[?id != ''][].id".format(artist_id),feat_tracks)
    print(feat_artists)

    #si pas de tracks avec le nom de l'artiste et du featuring, cest que le titre est par l'artiste principal de l'album
    if feat_artists == []:
        print("no feat artist, plugging album artists")
        feat_artists = jmespath.search("artists[?id != '{}' && name != 'Various'][].id".format(artist_id), album_infos)
        print(feat_artists)
    feat_extraartists = jmespath.search("[].extraartists[?role == 'Featuring' && id != '{}'][].id".format(artist_id),feat_tracks)
    print(feat_extraartists)
    
    order = random.choice([True,False])
    if order: 
        artists_id = feat_artists + feat_extraartists
    else :
        artists_id = feat_extraartists + feat_artists
    print(artists_id)
    
    #on loope à travers les artistes pour vérifier qu'ils sont bien des rappeurs français, on sélectionne le premier qui est bon
    feat_json = None
    if artists_id != []:
        
        for feat in artists_id:
            global liste_rappeur_cités
            if (feat in liste_rappeur_cités) or (feat == "194") or (feat == '194'):
                print("on l'a déjà dit")
                continue
            else:
                print(feat)
                print("on ne l'a pas déjà dit")
            releases = get_artist_releases(feat)
            if check_rapper(releases):
                feat_json = (album_infos,feat)
                break
    #bout de code un peu inutile que je garde au cas où la situation où ma liste d'artistes est vide se présente
    else:
        print("no feat artist")
                 
        if ("genres" in album_infos) and ("country" in album_infos):
            genres= album_infos["genres"]
            country = album_infos["country"]
        else:
            
            return None

        if (country == "France") and ("Hip Hop" in genres):
            feat = jmespath.search("artists[?id != '{}' && name != 'Various'][].id | [0]".format(artist_id), album_infos)
            if feat not in liste_rappeur_cités:
                feat_json = (album_infos,feat)
            else:
                feat_json = None
        else:
            feat_json = None
    return feat_json


# on regarde les sorties sur lesquelles apparait un artiste un à un à la recherche d'un featuring 
def loop_through_releases(releases,role,artist_id):
    print("we are now in the loop function")
    selected_releases = jmespath.search("[?role == '{}'].resource_url".format(role),releases)

    if len(selected_releases) > 0:
        feat_json = None
        random.shuffle(selected_releases)

        for album_url in selected_releases:
            if role == "Main":
                feat_json = get_main_featuring(album_url)
                print("main feature gotten")
            elif role == "Appearance":
                feat_json = get_appearance_featuring(album_url,artist_id)
                print("appearance feature gotten")
            
            if feat_json != None:
                break
        return feat_json
    else :
        return None

#les artistes sur discogs ont parfois des noms incorrects, on les corrige
def clean_name(to_clean):
    
    def replace(string):
        replacer = re.sub("\(\d+\)","",string).strip()
        return replacer
    
    if isinstance(to_clean,list):
        cleaned = [replace(name) for name in to_clean]
        
    elif isinstance(to_clean,str):
        cleaned = replace(to_clean)
    else:
        
        print("Weird Sheet happening")
        print(type(to_clean))
        cleaned = to_clean
    return cleaned
    
#récupérer le nom d'un artiste à partir de son id sur discogs
def get_name(artist_id):
    url = "https://api.discogs.com/artists/{}".format(artist_id) + "?" + secrets
    response = wait_request(url)
    name = response.json()["name"]
    name = clean_name(name)
    return name


#une fois qu'on a trouver notre featuring on récupère toutes les infos dont a besoin pour notre tweet
def get_featuring_info(feat_json,artist_id,role):
    test_album_info = feat_json
    print("we are now in the get_featuring_info function ")
    
    
    album_infos = feat_json[0]
    other_artist = feat_json[1]
    
    infos = {}
    
    artists_album = jmespath.search("artists[].name",album_infos)
    infos["artists_album"] = ", ".join(clean_name(artists_album))
    
    infos["album_title"] = album_infos["title"]
    infos["year"] = album_infos["year"]
    infos["url"] = album_infos["uri"]
    
    if role == "Main":
        
        
        track = jmespath.search("tracklist[?extraartists[?id == '{}' && role == 'Featuring']] | [0]".format(other_artist),album_infos)
        infos["previous_rappeur"] = clean_name(jmespath.search("artists[?id == '{}'].name".format(artist_id) ,album_infos)[0])
        
    elif role == "Appearance":
        tracks = jmespath.search("tracklist[?extraartists[?id == '{}' && role == 'Featuring']]".format(artist_id),album_infos)
        track_artists = jmespath.search("[].artists[].id" ,tracks)
        if (track_artists != None) and (len(track_artists) > 1) and (other_artist in track_artists):
            
            track = jmespath.search("tracklist[?extraartists[?id == '{}'] && artists[?id == '{}']] | [0]".format(artist_id,other_artist),album_infos)
            
        else:
            
            track = jmespath.search("tracklist[?extraartists[?id == '{}']] | [0]".format(artist_id),album_infos) 
        name_toclean = jmespath.search("extraartists[?id == '{}'][].name | [0]".format(artist_id) ,track)
        infos["previous_rappeur"] = clean_name(name_toclean)
        
    infos["track_name"] = track["title"]
    
    track_artists = jmespath.search("artists[].name" ,track)
    if track_artists == None:
        infos["track_artists"] = infos["artists_album"]
    
    else:
        my_artist = jmespath.search("extraartists[?id == '{}'][].name | [0]".format(artist_id) ,track)
        infos["track_artists"] = ", ".join(clean_name(track_artists))
    
    track_extraartists = jmespath.search("extraartists[?role == 'Featuring'][].name" ,track)
    infos["extraartists"] = ", ".join(track_extraartists)
    
    
    infos["other_artist_id"] = other_artist
    infos["next_rappeur"] = get_name(other_artist)
    
    
    infos["image"] = jmespath.search("images[0].uri",album_infos)
        
    
    
    print("featuring infos loaded")
    return infos



#On transforme l'image pour qu'elle colle aux normes de twitter
def resize_with_pad(im, target_width, target_height):
    '''
    Resize PIL image keeping ratio and using white background.
    '''
    target_ratio = target_height / target_width
    im_ratio = im.height / im.width
    if target_ratio > im_ratio:
        # It must be fixed by width
        resize_width = target_width
        resize_height = round(resize_width * im_ratio)
    else:
        # Fixed by height
        resize_height = target_height
        resize_width = round(resize_height / im_ratio)

    image_resize = im.resize((resize_width, resize_height), Image.ANTIALIAS)
    background = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 255))
    offset = (round((target_width - resize_width) / 2), round((target_height - resize_height) / 2))
    background.paste(image_resize, offset)
    return background.convert('RGB')

#fonction principale qui combine toutes les fonctions précédentes pour trouver le featuring et récupérer les infos
def get_featuring(artist_id):
    
    
    releases = get_artist_releases(artist_id,full=True)
    
    #on choisit de commencer soit par les sorties principales soit les apparitions chez d'autres artistes
    roles = ["Main",'Appearance']
    role = random.choice(roles)
    print("role chosen : ", role)
    roles.remove(role)
    
    result = loop_through_releases(releases,role,artist_id)
    
    # si pas de résultat pour le premier rôle choisi, on réésaye avec l'autre rôle
    if result == None:
        print("result is none")
        role = roles[0]
        print(role)
        result = loop_through_releases(releases,role,artist_id)
        
        if result != None:
            print("second loop was successfull")
            feats_infos = get_featuring_info(result,artist_id,role)
        else:
            feats_infos = None
    
    #si on a trouve un feat on récupére les infos du feat
    else :
        print("first loop was succesfull")
        
        feats_infos = get_featuring_info(result,artist_id,role)
        
    
    feat_infos = feats_infos
    
    #si on a trouvé un feat, on tweet le feat
    if feat_infos != None:
        
        params = {}
        nb_echanges = len(tracking_file["manches"][-1]["rappeurs"])
        nb_manches = len(tracking_file["manches"])
        if nb_echanges == 1:
            intro = f"Manche n°{nb_manches}. \n\n"
        else:
            intro= ""
            
        status = f"""{intro}{clean_name(feat_infos["previous_rappeur"])}  ---->   {clean_name(feat_infos["next_rappeur"])}\n\n{clean_name(feat_infos["track_artists"])} Feat. {clean_name(feat_infos["extraartists"])}  -  {feat_infos["track_name"]}
        \n\nAlbum : {clean_name(feat_infos["artists_album"])} - {feat_infos["album_title"]} - {feat_infos["year"]}\n{feat_infos["url"]}
       
        """
          
        params["status"] = status
        
        
       # on essaye de récupérer et traiter l'image, sinon on n'en met pas
        try:
            print(params)
            image = Image.open(requests.get(feat_infos["image"],stream=True).raw)
            im_resize = resize_with_pad(image,1024, 512)
            print(image.size)
            
            
            buf = io.BytesIO()
            im_resize.save(buf, format='JPEG')
            img = buf.getvalue()

            url = "https://upload.twitter.com/1.1/media/upload.json"

            files = {"media" : img}
            req_media = requests.post(url, files = files,auth=auth)
            img_id = req_media.json()["media_id"]
            print("img_id : ", img_id)
            params["media_ids"] =  img_id
            print(params)

            
        except Exception as e:
            print(e)
            print("no picture")
        
        #on tweet le tweet
        print("send tweet")
        print(params)
        url = "https://api.twitter.com/1.1/statuses/update.json"
        r = requests.post(url,params=params,auth=auth)
        print(r)
        
        return feat_infos["other_artist_id"]
    else:
     
        return None

#on récupère le dernier tweet, si c'était une fin de match on commence un nouveau match
def get_last_pass_id():
    print("get_last_pass function")
    
    url ="https://api.twitter.com/1.1/statuses/user_timeline.json"
    params = {"name" : "RolandGamosBot", "user_id" : "1360353237220655104"}
    last_tweet = requests.get(url,params=params,auth=auth).json()[0]
    if 'Manche' in last_tweet["text"]:
        tweet_id = last_tweet["id"]
    else:
        tweet_id = None
    return tweet_id

    
#fonction qui exécute la manche
def passe():
    load_data()
    
    print(liste_rappeur_cités)
    #si pas de rappeur, on en met un. 
    if liste_rappeur_cités == []:
        
        input_rappeur = random.choice(([i[1]["id"] for i in tracking_file["rappeurs_select"].items()]))
        liste_rappeur_cités.append(str(input_rappeur))
    else:
        input_rappeur = liste_rappeur_cités[-1]
    
    #on trouve le prochain rappeur et on l'ajoute à note liste
    next_rappeur = get_featuring(input_rappeur)
    liste_rappeur_cités.append(str(next_rappeur))
    print(liste_rappeur_cités)
       
    tracking_file["manches"][-1]["rappeurs"] = liste_rappeur_cités
    
    #sinon on conclut la manche
    if (next_rappeur == 'None') or (next_rappeur == None):
        
        tracking_file["manches"][-1]["end_date"] = str(time.time())
        tracking_file["manches"].append({})
        
        next_random = random.choice(([i[1] for i in tracking_file["rappeurs_select"].items()]))
        next_rappeur = str(next_random["id"])
        next_name = clean_name(next_random["name"])
        
        tracking_file["manches"][-1]["rappeurs"] = [next_rappeur]
        
        previous_name = get_name(input_rappeur)
        
        sentence1 = f"{previous_name}  -----> 5, 4, 3, 2, 1.... Manche terminée!\n\n" 

        sentence2 = f"Nombre d'échanges : {len(liste_rappeur_cités)}. "


        sentence3 = f"\n\nProchain rappeur : {next_name} "

        panache = ""
        if len(liste_rappeur_cités) > 20:
            panache = "Quel panache!"

        status = sentence1  + sentence2 + panache + sentence3
        url = "https://api.twitter.com/1.1/statuses/update.json"
        params = {"status" : status}
        tweet_id = get_last_pass_id()
        params["in_reply_to_status_id"] = tweet_id
        
        requests.post(url,params=params,auth=auth)
        
        
        
        encore = False
    else:
        encore = True
    
    
    # on sauvegarde nos données
    data=json.dumps(tracking_file)
    s3.Bucket('rolandgamos').put_object(Key='roland_gamos.json', Body=data)
    return encore



