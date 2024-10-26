docker stack rm mewbie
python3 container_setup.py
docker stack deploy --compose-file docker-compose.yml mewbie
