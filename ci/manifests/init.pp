$packages = [ 'libsasl2-dev', 'python-dev', 'libldap2-dev', 'libssl-dev' ]

package { $packages: ensure => 'installed' }
