import jenkins_badges

#path to your jenkins instance
base_url = "http://localhost:8080/"

# not required if anonymous jenkins user has read access
username = "admin" #a user with read access
token = "aa43ee82572fe77467e942a69fefabf1" #user's token

app = jenkins_badges.create_app(base_url=base_url,
                          username=username,
                          token=token)

app.run(host = '0.0.0.0', port=9000)