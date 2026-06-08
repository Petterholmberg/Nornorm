
//-- Skapa service account
CREATE USER app_service WITH PASSWORD 'ett_starkt_lösenord';


//-- Ge anslutningsrättigheter
// byt mindb mot databasen
GRANT CONNECT ON DATABASE mindb TO app_service;
GRANT USAGE ON SCHEMA public TO app_service;

//-- Ge bara nödvändiga rättigheter
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_service;


//-- Gäller även framtida tabeller
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_service;
 
