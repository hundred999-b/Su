#!/usr/bin/env bash

set +e

PROJECT_ROOT="$(pwd)"
REPORT="FULL_AUDIT_$(date +%Y%m%d_%H%M%S).txt"

exec > >(tee "$REPORT") 2>&1

echo "============================================================"
echo "                 SHOPU FULL PRODUCTION AUDIT"
echo "============================================================"
echo "Project: $PROJECT_ROOT"
echo "Date:    $(date)"
echo

section() {
    echo
    echo "============================================================"
    echo " $1"
    echo "============================================================"
}

run_check() {
    echo
    echo "+ $*"
    "$@"
    rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "[PASS] exit=$rc"
    else
        echo "[WARN/FAIL] exit=$rc"
    fi
}

section "1. ENVIRONMENT"

run_check python --version
run_check python -c 'import django; print("Django:", django.get_version())'
run_check python -c 'import psycopg; print("psycopg:", psycopg.__version__)'

section "2. PROJECT STRUCTURE"

for d in accounts adminpanel audit banktransfer crypto escrow finance \
         giftcards ledger marketplace payments referrals reviews security \
         stage4 support telegram_integration vendor_verification withdrawals
do
    if [ -d "$d" ]; then
        echo "[PASS] $d/"
    else
        echo "[WARN] Missing $d/"
    fi
done

section "3. DJANGO SYSTEM CHECK"

python manage.py check
echo "Exit code: $?"

section "4. MIGRATIONS"

python manage.py showmigrations
echo
python manage.py migrate --plan

section "5. DATABASE CONNECTION"

python - <<'PY'
import os
import sys

try:
    import psycopg

    url = os.environ.get("DATABASE_URL")

    if not url:
        print("[WARN] DATABASE_URL is not set")
        sys.exit(1)

    with psycopg.connect(url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    current_user,
                    current_database(),
                    version()
            """)
            user, database, version = cur.fetchone()

            print("[PASS] Database connection")
            print("User:", user)
            print("Database:", database)
            print("PostgreSQL:", version.split(",")[0])

except Exception as exc:
    print("[FAIL] Database connection")
    print(type(exc).__name__ + ":", str(exc))
PY

section "6. DATABASE URL SAFETY"

if [ -n "$DATABASE_URL" ]; then
    echo "$DATABASE_URL" |
        sed -E 's#(postgresql://[^:]+:)[^@]+@#\1REDACTED@#'
else
    echo "[WARN] DATABASE_URL is not set"
fi

section "7. PIN / OTP / RECOVERY SECURITY"

if [ -d security ]; then
    echo "--- security files ---"
    find security -maxdepth 2 -type f \
        ! -path '*/__pycache__/*' \
        -print
fi

echo
echo "--- security implementation indicators ---"
grep -RniE \
'check_password|make_password|PBKDF2|argon2|bcrypt|hash|OTP|otp|PIN|pin|recovery|one.?time|expires|expiry|attempt' \
security accounts --include='*.py' 2>/dev/null | head -n 250

section "8. DANGEROUS PLAINTEXT SECRET INDICATORS"

echo "Searching source for common hard-coded secret patterns."
echo "This is only an indicator scan; manually review results."

grep -RniE \
'password[[:space:]]*=[[:space:]]*["'\''][^"'\'']+|SECRET_KEY[[:space:]]*=[[:space:]]*["'\'']|api[_-]?key[[:space:]]*=[[:space:]]*["'\'']|token[[:space:]]*=[[:space:]]*["'\''][A-Za-z0-9_-]{12,}|private[_-]?key' \
. \
--include='*.py' \
--include='*.env' \
--include='*.json' \
--include='*.yaml' \
--include='*.yml' \
--exclude-dir='.git' \
--exclude-dir='__pycache__' \
2>/dev/null | head -n 250

section "9. DEBUG / PRODUCTION SETTINGS"

grep -RniE \
'DEBUG[[:space:]]*=|ALLOWED_HOSTS|CSRF_TRUSTED_ORIGINS|SECURE_SSL_REDIRECT|SESSION_COOKIE_SECURE|CSRF_COOKIE_SECURE|SECURE_HSTS|SECURE_CONTENT_TYPE_NOSNIFF|SECURE_REFERRER_POLICY' \
. \
--include='*.py' \
--exclude-dir='.git' \
--exclude-dir='__pycache__' \
2>/dev/null | head -n 300

section "10. AUTHORIZATION / PERMISSIONS"

grep -RniE \
'permission|permissions|is_staff|is_superuser|has_perm|login_required|PermissionDenied|@permission_required|allowed|authorize' \
accounts adminpanel withdrawals payments marketplace vendor_verification support \
--include='*.py' \
2>/dev/null | head -n 350

section "11. TRANSACTIONS / CONCURRENCY"

grep -RniE \
'transaction\.atomic|select_for_update|IntegrityError|idempotency|unique_together|UniqueConstraint|atomic' \
ledger withdrawals payments escrow banktransfer giftcards \
--include='*.py' \
2>/dev/null | head -n 400

section "12. LEDGER / WALLET"

if [ -d ledger ]; then
    find ledger -maxdepth 2 -type f \
        ! -path '*/__pycache__/*' \
        -print

    echo
    grep -RniE \
    'balance|credit|debit|ledger|wallet|idempotency|reference' \
    ledger --include='*.py' \
    2>/dev/null | head -n 350
fi

section "13. WITHDRAWALS"

if [ -d withdrawals ]; then
    sed -n '1,240p' withdrawals/services.py
fi

section "14. PAYMENTS / IDEMPOTENCY"

grep -RniE \
'idempotency|payment|gateway|webhook|signature|verify|transaction' \
payments banktransfer crypto finance \
--include='*.py' \
2>/dev/null | head -n 400

section "15. ESCROW"

grep -RniE \
'escrow|lock|release|refund|settle|dispute' \
escrow --include='*.py' \
2>/dev/null | head -n 300

section "16. GIFT CARDS"

grep -RniE \
'gift.?card|top.?up|redeem|balance|proof' \
giftcards --include='*.py' \
2>/dev/null | head -n 250

section "17. REFERRALS"

grep -RniE \
'referral|commission|reward|bonus|credit' \
referrals --include='*.py' \
2>/dev/null | head -n 250

section "18. VENDOR VERIFICATION"

grep -RniE \
've[r]?ification|trust|seller|vendor|evidence|review|approve|reject' \
vendor_verification --include='*.py' \
2>/dev/null | head -n 300

section "19. AUDIT LOGGING"

grep -RniE \
'audit|AuditLog|logging|logger|security_event|event' \
audit accounts adminpanel security withdrawals payments \
--include='*.py' \
2>/dev/null | head -n 300

section "20. TELEGRAM INTEGRATION"

if [ -d telegram_integration ]; then
    find telegram_integration -maxdepth 2 -type f \
        ! -path '*/__pycache__/*' \
        -print

    echo
    grep -RniE \
    'telegram|bot|webhook|secret|token|notification' \
    telegram_integration --include='*.py' \
    2>/dev/null | head -n 300
fi

section "21. SUPPORT / ABUSE CONTROLS"

grep -RniE \
'rate|limit|throttle|abuse|spam|support|message' \
support --include='*.py' \
2>/dev/null | head -n 300

section "22. DATABASE CONSTRAINTS / INDEXES"

grep -RniE \
'UniqueConstraint|unique=True|CheckConstraint|Index\(|indexes|constraints' \
. \
--include='models.py' \
--include='*.py' \
--exclude-dir='.git' \
--exclude-dir='__pycache__' \
2>/dev/null | head -n 400

section "23. MIGRATION FILES"

find . -path '*/migrations/*.py' \
    ! -name '__init__.py' \
    ! -path '*/__pycache__/*' \
    | sort

section "24. TEST INVENTORY"

echo "Test files:"
find . \
    \( -name 'tests.py' -o -name 'test_*.py' -o -path '*/tests/*.py' \) \
    ! -path '*/__pycache__/*' \
    | sort

echo
echo "Test count currently discovered by Django:"
python manage.py test --keepdb --verbosity 0
TEST_RC=$?
echo "Full test exit code: $TEST_RC"

section "25. PYTHON SYNTAX CHECK"

python -m compileall -q \
    accounts adminpanel audit banktransfer crypto escrow finance \
    giftcards ledger marketplace payments referrals reviews security \
    stage4 support telegram_integration vendor_verification withdrawals

echo "compileall exit code: $?"

section "26. DEPENDENCIES"

if [ -f requirements.txt ]; then
    echo "--- requirements.txt ---"
    cat requirements.txt
else
    echo "[INFO] requirements.txt not found"
fi

echo
python -m pip check
echo "pip check exit code: $?"

section "27. GIT / ACCIDENTAL SECRET TRACKING"

if [ -d .git ]; then
    echo "--- git status ---"
    git status --short

    echo
    echo "--- potentially sensitive tracked files ---"
    git ls-files | grep -Ei \
    '(^|/)(\.env|.*secret.*|.*credential.*|.*password.*|.*private.*key.*)$' \
    || true
else
    echo "[INFO] Git repository not detected"
fi

section "28. FILE PERMISSIONS"

find . -type f \
    \( -name '*.env' -o -name '*secret*' -o -name '*credential*' \) \
    ! -path '*/.git/*' \
    ! -path '*/__pycache__/*' \
    -print 2>/dev/null

section "29. DEBUG / TODO / FIXME REVIEW"

grep -RniE \
'TODO|FIXME|XXX|HACK|TEMP|DEBUG|print\(' \
. \
--include='*.py' \
--exclude-dir='.git' \
--exclude-dir='__pycache__' \
2>/dev/null | head -n 400

section "30. PRODUCTION FILES"

echo "--- common deployment files ---"

for f in \
    Dockerfile \
    docker-compose.yml \
    docker-compose.yaml \
    Procfile \
    gunicorn.conf.py \
    nginx.conf \
    .env.example \
    requirements.txt \
    pyproject.toml \
    manage.py
do
    if [ -f "$f" ]; then
        echo "[FOUND] $f"
    else
        echo "[MISSING] $f"
    fi
done

section "31. DJANGO DEPLOYMENT CHECK"

python manage.py check --deploy
DEPLOY_RC=$?
echo "Deployment check exit code: $DEPLOY_RC"

section "32. FINAL SUMMARY"

echo
echo "Audit report saved to:"
echo "$PROJECT_ROOT/$REPORT"
echo

echo "IMPORTANT:"
echo "- This audit does not modify application data."
echo "- This audit does not delete test_postgres."
echo "- Full tests are run with --keepdb."
echo "- Any WARN/FAIL requires review before production."
echo

echo "============================================================"
echo "                 END OF FULL AUDIT"
echo "============================================================"
