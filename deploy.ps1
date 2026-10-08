$SERVER = "root@39.105.81.165"
$TARGET = "/opt/trip-planner"

Write-Host "Deploying..." -ForegroundColor Cyan

Write-Host "Creating remote dirs..." -ForegroundColor Yellow
ssh $SERVER "mkdir -p $TARGET/backend/app/agents $TARGET/backend/app/api/routes $TARGET/backend/app/models $TARGET/backend/app/services $TARGET/frontend/src/services $TARGET/frontend/src/types $TARGET/frontend/src/views"

Write-Host "Uploading docker-compose + env..." -ForegroundColor Yellow
scp .\docker-compose.yml .\.env.production ${SERVER}:${TARGET}/

Write-Host "Uploading backend..." -ForegroundColor Yellow
scp .\backend\run.py .\backend\requirements.txt .\backend\Dockerfile .\backend\.dockerignore ${SERVER}:${TARGET}/backend/
scp .\backend\app\*.py ${SERVER}:${TARGET}/backend/app/
scp .\backend\app\agents\*.py ${SERVER}:${TARGET}/backend/app/agents/
scp .\backend\app\api\*.py ${SERVER}:${TARGET}/backend/app/api/
scp .\backend\app\api\routes\*.py ${SERVER}:${TARGET}/backend/app/api/routes/
scp .\backend\app\models\*.py ${SERVER}:${TARGET}/backend/app/models/
scp .\backend\app\services\*.py ${SERVER}:${TARGET}/backend/app/services/

Write-Host "Uploading frontend..." -ForegroundColor Yellow
scp .\frontend\package.json .\frontend\package-lock.json .\frontend\index.html .\frontend\vite.config.ts .\frontend\tsconfig.json .\frontend\Dockerfile .\frontend\nginx.conf .\frontend\.dockerignore ${SERVER}:${TARGET}/frontend/
scp .\frontend\src\*.ts .\frontend\src\*.vue ${SERVER}:${TARGET}/frontend/src/
scp .\frontend\src\services\*.ts ${SERVER}:${TARGET}/frontend/src/services/
scp .\frontend\src\types\*.ts ${SERVER}:${TARGET}/frontend/src/types/
scp .\frontend\src\views\*.vue ${SERVER}:${TARGET}/frontend/src/views/

Write-Host "Upload done!" -ForegroundColor Green
Write-Host ""
Write-Host "Next: ssh root@39.105.81.165" -ForegroundColor Cyan
Write-Host "      cd /opt/trip-planner" -ForegroundColor Cyan
Write-Host "      docker compose up -d --build" -ForegroundColor Cyan
