CREATE USER tool_user WITH PASSWORD 'tool_user_password';
CREATE DATABASE tools_database OWNER tool_user;
GRANT ALL PRIVILEGES ON DATABASE tools_database TO tool_user;
