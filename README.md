## RolandGamosBot
A twitter bot that plays a game known as *"Roland Gamos"* which is part of the french gameshow [Rap Jeu](https://www.youtube.com/playlist?list=PLLkvlAQ5R3l8zLZWcwcjkMQ1pU4BQlAcp) : 

[@RolandGamosBot](https://twitter.com/RolandGamosBot) 

We select a first french rapper, then look for other rappers he has done a featuring with. We select one of them that has not yet been cited during the game. Then for this new rapper, we repeat the process by looking for another rapper he has made a featuring with and so forth until we can't find a featuring and start a new game.

Stack:

I tried to use as little extra libraries as possible to keep my environment light.
- Discogs and twitter APIs, simply queried with the requests library.
- I chose not to use Pandas or Numpy at all because they're too heavy, which was a challenge for me as a data analyst. Instead I used base python and the wonderful json querying library [Jmsepath](https://jmespath.org/).
- I deployed it as an AWS lambda function and stored my data in a AWS s3 bucket.

The code is a bit long and messy because I didn't take the time to make it shorter but it works and no one else than me needs to maintain it.
