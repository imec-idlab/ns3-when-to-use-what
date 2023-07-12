build_lib(
  LIBNAME veloce-addons
  SOURCE_FILES
    helper/ap-server-helper.cc
    model/packet-tag.cc
    model/ap-server.cc
    model/sta-client.cc
  HEADER_FILES
  helper/ap-server-helper.h
    model/packet-tag.h
    model/ap-server.h
    model/sta-client.h
  LIBRARIES_TO_LINK ${libinternet}
                    ${libstats}
)
