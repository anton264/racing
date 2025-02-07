#!/usr/bin/env bash
set -x
PG_CLUSTER_USER_SECRET_NAME=db-pguser-free-practice
PG_CLUSTER_USER_SECRET_NAME=db-pguser-paddock
PG_CLUSTER_USER_SECRET_NAME=db-pguser-paddock-root
HOST=$(kubectl get routes/telemetry --template='{{ .spec.host }}')

oc project b4mad-racing

PGPASSWORD=$(kubectl get secrets "${PG_CLUSTER_USER_SECRET_NAME}" -o go-template='{{.data.password | base64decode}}') \
PGUSER=$(kubectl get secrets "${PG_CLUSTER_USER_SECRET_NAME}" -o go-template='{{.data.user | base64decode}}') \
PGDATABASE=$(kubectl get secrets "${PG_CLUSTER_USER_SECRET_NAME}" -o go-template='{{.data.dbname | base64decode}}') \
/opt/homebrew/bin/psql -h $HOST -p 31884
