# name this file as secrets.py
smtp_host = "your.smtp.server"
smtp_user = "your.smtp.user"
smtp_password = "your.smtp.password"

from_mail = "frommail@mail.it"
to_mail = "tomail@mail.it"

choco_local = "https://myrepo.it/chocolatey" 
choco_local_latest_repo = "https://myrepo.it/chocolatey/Packages?$filter=IsLatestVersion"
choco_local_push_key = "KEY"

choco_community_pkg = 'https://chocolatey.org/api/v2/FindPackagesById()?id=%27{}%27&$filter=IsLatestVersion'
choco_community_download = "https://myrepo.it/api/v2/package/{}/{}"

temp_folder = '/path/to/somewhere/temp/folder'
folder_separator = '/'
pkg_extension = '.nupkg'

db_path = '/path/to/somewhere/choco_update.db'
