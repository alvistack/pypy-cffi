%global debug_package %{nil}

Name: python-cffi
Epoch: 100
Version: 1.14.6
Release: 1%{?dist}
Summary: Foreign Function Interface for Python to call C code
License: MIT
URL: https://pypi.org/project/cffi/#history
Source0: %{name}_%{version}.orig.tar.gz
BuildRequires: fdupes
BuildRequires: libffi-devel
BuildRequires: python-rpm-macros
BuildRequires: python3-cython
BuildRequires: python3-devel
BuildRequires: python3-setuptools

%description
Foreign Function Interface for Python, providing a convenient and
reliable way of calling existing C code from Python. The interface is
based on LuaJIT’s FFI.

%prep
%autosetup -T -c -n %{name}_%{version}-%{release}
tar -zx -f %{S:0} --strip-components=1 -C .

%build
%py3_build

%install
%py3_install
find %{buildroot}%{python3_sitearch} -type f -name '*.pyc' -exec rm -rf {} \;
fdupes -qnrps %{buildroot}%{python3_sitearch}

%check

%if 0%{?suse_version} > 1500 || 0%{?centos_version} == 700
%package -n python%{python3_version_nodots}-cffi
Summary: Foreign Function Interface for Python to call C code
Requires: python3
Requires: python3-pycparser
Provides: python3-cffi = %{epoch}:%{version}-%{release}
Provides: python3dist(cffi) = %{epoch}:%{version}-%{release}
Provides: python%{python3_version}-cffi = %{epoch}:%{version}-%{release}
Provides: python%{python3_version}dist(cffi) = %{epoch}:%{version}-%{release}
Provides: python%{python3_version_nodots}-cffi = %{epoch}:%{version}-%{release}
Provides: python%{python3_version_nodots}dist(cffi) = %{epoch}:%{version}-%{release}

%description -n python%{python3_version_nodots}-cffi
Foreign Function Interface for Python, providing a convenient and
reliable way of calling existing C code from Python. The interface is
based on LuaJIT’s FFI.

%files -n python%{python3_version_nodots}-cffi
%license LICENSE
%{python3_sitearch}/_cffi_backend.*.so
%{python3_sitearch}/cffi*
%endif

%if !(0%{?suse_version} > 1500) && !(0%{?centos_version} == 700)
%package -n python3-cffi
Summary: Foreign Function Interface for Python to call C code
Requires: python3
Requires: python3-pycparser
Provides: python3-cffi = %{epoch}:%{version}-%{release}
Provides: python3dist(cffi) = %{epoch}:%{version}-%{release}
Provides: python%{python3_version}-cffi = %{epoch}:%{version}-%{release}
Provides: python%{python3_version}dist(cffi) = %{epoch}:%{version}-%{release}
Provides: python%{python3_version_nodots}-cffi = %{epoch}:%{version}-%{release}
Provides: python%{python3_version_nodots}dist(cffi) = %{epoch}:%{version}-%{release}

%description -n python3-cffi
Foreign Function Interface for Python, providing a convenient and
reliable way of calling existing C code from Python. The interface is
based on LuaJIT’s FFI.

%files -n python3-cffi
%license LICENSE
%{python3_sitearch}/_cffi_backend.*.so
%{python3_sitearch}/cffi*
%endif

%changelog
