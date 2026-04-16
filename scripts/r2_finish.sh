#!/bin/bash
# Wait for character upload to finish, then upload moves, then cleanup
echo "Waiting for character upload to finish..."
while ps aux | grep "upload_to_r2.py characters" | grep -v grep > /dev/null 2>&1; do
    sleep 30
done
echo "Character upload done! Starting move images..."

# Upload move images
python3 -u /Users/pouriamousavi/Documents/RPG/scripts/upload_to_r2.py moves >> /tmp/r2_upload.log 2>&1
echo "Move images done!"

# Cleanup: remove old Supabase Storage URLs from metadata, keep only R2 ones
python3 -u -c "
import urllib.request, json

SUPABASE_URL = 'https://vfvljfwcrwvxttmxxzfa.supabase.co'
KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmdmxqZndjcnd2eHR0bXh4emZhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxNjQ0MDQsImV4cCI6MjA5MDc0MDQwNH0.MLeA_Gk_IC9YmfJepdhSyXUQ7gPS8SnfDb7fA4hIqx0'
HEADERS = {'apikey': KEY, 'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}

# Delete old Supabase Storage entries (source = 'bulk_import'), keep R2 ones (source = 'r2_bulk_import')
for table in ['character_images', 'move_images']:
    url = f'{SUPABASE_URL}/rest/v1/{table}?source=eq.bulk_import'
    req = urllib.request.Request(url, headers=HEADERS, method='DELETE')
    try:
        resp = urllib.request.urlopen(req)
        print(f'Cleaned old {table} entries')
    except Exception as e:
        print(f'Error cleaning {table}: {e}')

# Verify counts
for table in ['character_images', 'move_images']:
    url = f'{SUPABASE_URL}/rest/v1/{table}?select=source'
    headers = {**HEADERS, 'Prefer': 'count=exact', 'Range': '0-0'}
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req)
    cr = resp.headers.get('Content-Range', '?')
    print(f'{table}: {cr}')
" 2>&1

echo ""
echo "=== ALL DONE ==="
echo "Check /tmp/r2_upload.log for full details"
tail -5 /tmp/r2_upload.log
