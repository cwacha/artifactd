%define app_user artifactd
%define app_group artifactd

Summary:	Artifactd
Name:		artifactd
Version:	%{app_version}
Release:	%{app_revision}
Group:		System Environment/Daemon
License:	GPL-3.0
URL:		http://wacha.ch/atrifactd
AutoReqProv:	no
BuildRoot:	%_topdir/BUILD

%description
Artifactd adf adf asdf asf 


%files
%defattr(-,%app_user,%app_group)
/opt/artifactd
%attr(755,root,root) /usr/lib/systemd/system/*

%clean
:

%pre
if [ "$1" = "1" ]; then
	echo "##### preinstall %{app_version}-%{app_revision}"
elif [ "$1" = "2" ]; then
	echo "##### preinstall %{app_version}-%{app_revision} during upgrade"
fi

echo "##### creating user and group if necessary"
getent group %{app_group} >/dev/null || groupadd %{app_group}
getent passwd %{app_user} >/dev/null || useradd %{app_user} -g %{app_group}

echo "##### done pre"

%post
if [ "$1" = "1" ]; then
	echo "##### postinstall %{app_version}-%{app_revision}"
elif [ "$1" = "2" ]; then
	echo "##### postinstall %{app_version}-%{app_revision} during upgrade"
fi

echo "##### Start general post installation."
systemctl enable artifactd
systemctl start artifactd
echo "##### done post"

%preun
if [ "$1" = "0" ]; then
	echo "##### pre uninstall %{app_version}-%{app_revision}"
	systemctl stop artifactd
	systemctl disable artifactd
elif [ "$1" = "1" ]; then
	echo "##### pre uninstall %{app_version}-%{app_revision} during upgrade"
fi
echo "##### done preun"

%postun
if [ "$1" = "0" ]; then
	echo "##### post uninstall %{app_version}-%{app_revision}"
elif [ "$1" = "1" ]; then
	echo "##### post uninstall %{app_version}-%{app_revision} during upgrade"
fi
echo "##### done postun"


