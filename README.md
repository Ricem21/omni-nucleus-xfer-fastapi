# TBD

## Requirments
## Build
```
docker build -t onxf .
```
## Run
```
docker compose down
docker compose up 
docker compose up -d
```

```
$ curl http://localhost:8000/status
{"status":"OK"}
```

```
curl -X POST  http://localhost:8000/files -H 'Filename: Mike.usd'
```

```
curl -X POST  http://localhost:8000/files -H 'Filename: test-data00dfads.usd' -H 'Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryyEmKNDsBKjB7QEqu'
```

TBD
