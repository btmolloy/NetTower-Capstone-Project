code/backEnd/storage/mongo_client.py

Purpose: Centralize MongoDB connection, collection handles, and index creation.
Inputs:

Mongo URI, DB name from config
Outputs:

Connected Mongo client + collection handles (hosts, edges, etc.)

Ensures indexes exist (e.g., on macs, ips, host_id, edge keys)