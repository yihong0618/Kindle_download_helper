#!/usr/bin/python
# -*- coding: utf8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals

__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


ANY = None
TF = {False, True}


PACKAGE_VERSION_PLACEHOLDERS = {
    "PackageVersion:YJReaderSDK-1.0.x.x GitSHA:c805492 Month-Day:04-22",
    "PackageVersion:YJReaderSDK-1.0.x.x GitSHA:[33mc805492[m Month-Day:04-22",
    "kfxlib-00000000",
}


KNOWN_KFX_GENERATORS = {
    ("2.16", "PackageVersion:YJReaderSDK-1.0.824.0 Month-Day:04-09"),
    ("3.41.1.0", "PackageVersion:YJReaderSDK-1.0.1962.11 Month-Day:10-17"),
    ("3.42.1.0", "PackageVersion:YJReaderSDK-1.0.2044.4 Month-Day:10-28"),
    ("6.11.1.2", "PackageVersion:YJReaderSDK-1.0.2467.43 Month-Day:07-05"),
    ("6.11.1.2", "PackageVersion:YJReaderSDK-1.0.2467.8 Month-Day:07-14"),
    ("6.11.1.2", "PackageVersion:YJReaderSDK-1.0.2539.3 Month-Day:03-17"),
    ("6.20.1.0", "PackageVersion:YJReaderSDK-1.0.2685.4 Month-Day:05-19"),
    ("6.24.1.0", "PackageVersion:YJReaderSDK-1.1.67.2 Month-Day:06-18"),
    ("6.28.1.0", "PackageVersion:YJReaderSDK-1.1.67.4 Month-Day:07-14"),
    ("6.28.2.0", "PackageVersion:YJReaderSDK-1.1.147.0 Month-Day:09-10"),
    ("7.38.1.0", "PackageVersion:YJReaderSDK-1.2.173.0 Month-Day:09-20"),
    ("7.45.1.0", "PackageVersion:YJReaderSDK-1.4.23.0 Month-Day:11-23"),
    ("7.58.1.0", "PackageVersion:YJReaderSDK-1.5.116.0 Month-Day:02-25"),
    ("7.66.1.0", "PackageVersion:YJReaderSDK-1.5.185.0 Month-Day:04-13"),
    ("7.66.1.0", "PackageVersion:YJReaderSDK-1.5.195.0 Month-Day:04-20"),
    ("7.91.1.0", "PackageVersion:YJReaderSDK-1.5.566.6 Month-Day:11-03"),
    ("7.91.1.0", "PackageVersion:YJReaderSDK-1.5.595.1 Month-Day:11-30"),
    ("7.111.1.1", "PackageVersion:YJReaderSDK-1.6.444.0 Month-Day:02-27"),
    ("7.111.1.1", "PackageVersion:YJReaderSDK-1.6.444.5 Month-Day:03-20"),
    ("7.121.3.0", "PackageVersion:YJReaderSDK-1.6.444.18 Month-Day:05-02"),
    ("7.125.1.0", "PackageVersion:YJReaderSDK-1.6.444.24 Month-Day:06-01"),
    ("7.125.1.0", "PackageVersion:YJReaderSDK-1.6.444.33 Month-Day:06-16"),
    ("7.131.2.0", "PackageVersion:YJReaderSDK-1.6.444.36 Month-Day:07-10"),
    ("7.135.2.0", "PackageVersion:YJReaderSDK-1.6.1034.2 Month-Day:08-23"),
    ("7.135.2.0", "PackageVersion:YJReaderSDK-1.6.1034.13 Month-Day:10-09"),
    ("7.135.2.0", "PackageVersion:YJReaderSDK-1.6.1034.17 Month-Day:11-06"),
    ("7.149.1.0", "PackageVersion:YJReaderSDK-1.6.1034.59 Month-Day:12-06"),
    ("7.149.1.0", "PackageVersion:YJReaderSDK-1.6.1034.62 Month-Day:12-21"),
    ("7.149.1.0", "PackageVersion:YJReaderSDK-1.6.1034.72 Month-Day:01-04"),
    ("7.149.1.0", "PackageVersion:YJReaderSDK-1.6.1871.0 Month-Day:01-23"),
    ("7.149.1.0", "PackageVersion:YJReaderSDK-1.6.1938.0 Month-Day:01-29"),
    ("7.149.1.0", "PackageVersion:YJReaderSDK-1.6.2071.0 Month-Day:02-12"),
    ("7.149.1.0", "PackageVersion:YJReaderSDK-1.6.200363.0 Month-Day:03-19"),
    ("7.153.1.0", ""),
    ("7.165.1.1", ""),
    ("7.168.1.0", ""),
    ("7.171.1.0", ""),
    ("7.174.1.0", ""),
    ("7.177.1.0", ""),
    ("7.180.1.0", ""),
    ("7.182.1.0", ""),
    ("7.188.1.0", ""),
    ("7.191.1.0", ""),
    ("7.213.1.0", ""),
    ("7.220.2.0", ""),
    ("7.228.1.0", ""),
    ("7.232.1.0", ""),
    ("7.236.1.0", ""),
    ("20.12.238.0", ""),
}


GENERIC_CREATOR_VERSIONS = {
    ("YJConversionTools", "2.15.0"),
    ("KTC", "1.0.11.1"),
    ("", ""),
}


KNOWN_FEATURES = {
    "symbols": {
        "max_id": {
            489,
            609,
            620,
            626,
            627,
            634,
            652,
            662,
            667,
            668,
            673,
            681,
            693,
            695,
            696,
            697,
            700,
            701,
            705,
            716,
            748,
            753,
            754,
            755,
            759,
            761,
            777,
            779,
            783,
            785,
            786,
            787,
            789,
            797,
            804,
            825,
        },
    },
    "format_capabilities": {
        "kfxgen.pidMapWithOffset": {1},
        "kfxgen.positionMaps": {2},
        "kfxgen.textBlock": {1},
        "db.schema": {1},
    },
    "SDK.Marker": {
        "CanonicalFormat": {
            1,
            2,
        },
    },
    "com.amazon.yjconversion": {
        "ar-reflow-language": {
            1,
        },
        "cn-reflow-language": {
            1,
        },
        "indic-reflow-language": {
            1,
        },
        "jp-reflow-language": {
            1,
        },
        "jpvertical-reflow-language": {
            2,
            3,
            4,
            5,
            6,
            7,
        },
        "reflow-language": {
            2,
            3,
        },
        "reflow-language-expansion": {
            1,
        },
        "tcn-reflow-language": {
            1,
        },
        "multiple_reading_orders-switchable": {
            1,
        },
        "reflow-section-size": ANY,
        "reflow-style": {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            (2147483646, 2147483647),
            (2147483647, 2147483647),
        },
        "yj_audio": {
            1,
            2,
        },
        "yj_custom_word_iterator": {
            1,
        },
        "yj_dictionary": {
            1,
            2,
        },
        "yj_double_page_spread": {
            1,
        },
        "yj_facing_page": {
            1,
        },
        "yj_fixed_layout": {
            1,
        },
        "yj_graphical_highlights": {
            1,
        },
        "yj_hdv": {
            1,
            2,
        },
        "yj_interactive_image": {
            1,
        },
        "yj_jpegxr_sd": {
            1,
        },
        "yj_jpg_rst_marker_present": {
            1,
        },
        "yj_mathml": {
            1,
        },
        "yj_mixed_writing_mode": {
            1,
            2,
        },
        "yj_non_pdf_fixed_layout": {
            2,
        },
        "yj_pdf_links": {
            1,
        },
        "yj_pdf_support": {
            1,
        },
        "yj_publisher_panels": {
            2,
        },
        "yj_rotated_pages": {
            1,
        },
        "yj_ruby": {
            1,
        },
        "yj_table": {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
        },
        "yj_table_viewer": {
            1,
            2,
        },
        "yj_textbook": {
            1,
        },
        "yj_thumbnails_present": {
            1,
        },
        "yj_vertical_text_shadow": {
            1,
        },
        "yj_video": {
            1,
        },
        "yj.conditional_structure": {
            1,
        },
        "yj.illustrated_layout": {
            1,
        },
    },
}


KNOWN_SUPPORTED_FEATURES = {
    ("$660",),
    ("$751",),
    ("$664", "crop_bleed", 1),
}


KNOWN_METADATA = {
    "book_navigation": {
        "pages": ANY,
    },
    "kindle_audit_metadata": {
        "file_creator": {
            "YJConversionTools",
            "FLYP",
            "KTC",
            "KC",
            "KPR",
        },
        "creator_version": {
            "2.15.0",
            "0.1.24.0",
            "0.1.26.0",
            "2.0.0.1",
            "1.0.11.1",
            "1.3.0.0",
            "1.5.14.0",
            "1.8.1.0",
            "1.9.2.0",
            "1.11.399.0",
            "1.11.539.0",
            "1.12.11.0",
            "1.13.7.0",
            "1.13.10.0",
            "0.93.187.0",
            "0.94.32.0",
            "0.95.8.0",
            "0.96.4.0",
            "0.96.40.0",
            "0.97.79.3",
            "0.98.260.0",
            "0.98.315.0",
            "0.99.28.0",
            "0.101.1.0",
            "0.102.0.0",
            "0.103.0.0",
            "1.0.319.0",
            "1.1.58.0",
            "1.2.83.0",
            "1.3.30.0",
            "1.4.200067.0",
            "1.5.60.0",
            "1.6.97.0",
            "1.7.223.0",
            "1.8.50.0",
            "1.9.52.0",
            "1.10.214.0",
            "1.11.576.0",
            "1.12.39.0",
            "1.14.112.0",
            "1.15.20.0",
            "1.16.2.0",
            "1.18.0.0",
            "1.20.1.0",
            "1.21.6.0",
            "1.22.13.0",
            "1.23.0.0",
            "1.24.33.0",
            "1.25.34.0",
            "1.26.14.0",
            "1.27.14.0",
            "1.28.12.0",
            "1.29.17.0",
            "1.30.4.0",
            "1.31.0.0",
            "1.32.1.0",
            "1.33.3.0",
            "1.34.20.0",
            "1.35.210.0",
            "1.35.618.0",
            "1.35.770.0",
            "1.36.1.0",
            "1.36.20.0",
            "1.37.2.0",
            "1.38.0.0",
            "1.38.37.0",
            "1.39.30.0",
            "1.40.6.0",
            "1.41.10.0",
            "1.42.2.0",
            "1.42.6.0",
            "1.43.0.0",
            "1.44.13.0",
            "1.45.20.0",
            "1.46.2.0",
            "1.47.1.0",
            "1.48.7.0",
            "1.49.0.0",
            "1.50.0.0",
            "1.51.1.0",
            "1.52.2.0",
            "1.52.4.0",
            "1.52.6.0",
            "1.53.1.0",
            "1.54.0.0",
            "1.55.0.0",
            "1.56.0.0",
            "1.57.0.0",
            "1.58.0.0",
            "1.59.0.0",
            "1.60.0.0",
            "1.60.1.0",
            "1.60.2.0",
            "1.61.0.0",
            "1.62.0.0",
            "1.62.1.0",
            "1.63.0.0",
            "3.0.0",
            "3.1.0",
            "3.2.0",
            "3.3.0",
            "3.4.0",
            "3.5.0",
            "3.6.0",
            "3.7.0",
            "3.7.1",
            "3.8.0",
            "3.9.0",
            "3.10.0",
            "3.10.1",
            "3.11.0",
            "3.12.0",
            "3.13.0",
            "3.14.0",
            "3.15.0",
            "3.16.0",
            "3.17.0",
            "3.17.1",
            "3.20.0",
            "3.20.1",
            "3.21.0",
            "3.22.0",
            "3.23.0",
            "3.24.0",
            "3.25.0",
            "3.26.0",
            "3.27.0",
            "3.28.0",
            "3.28.1",
            "3.29.0",
            "3.29.1",
            "3.29.2",
            "3.30.0",
            "3.31.0",
            "3.32.0",
            "3.33.0",
            "3.34.0",
            "3.35.0",
            "3.36.0",
            "3.36.1",
            "3.37.0",
            "3.38.0",
            "3.39.0",
            "3.39.1",
            "3.40.0",
            "3.41.0",
            "3.42.0",
            "3.43.0",
            "3.44.0",
            "3.45.0",
            "3.46.0",
            "3.47.0",
            "3.48.0",
            "3.49.0",
            "3.50.0",
            "3.51.0",
            "3.52.0",
            "3.52.1",
            "3.53.0",
            "3.54.0",
            "3.55.0",
            "3.56.0",
            "3.56.1",
            "3.57.0",
            "3.57.1",
            "3.58.0",
            "3.59.0",
            "3.59.1",
            "3.60.0",
            "3.61.0",
        },
    },
    "kindle_capability_metadata": {
        "continuous_popup_progression": {
            0,
        },
        "graphical_highlights": {1},
        "yj_double_page_spread": {1},
        "yj_facing_page": {1},
        "yj_fixed_layout": {1},
        "yj_has_animations": {1},
        "yj_illustrated_layout": {1},
        "yj_publisher_panels": {1},
        "yj_textbook": {1},
    },
    "kindle_ebook_metadata": {
        "book_orientation_lock": {"landscape", "portrait", "none"},
        "multipage_selection": {"disabled"},
        "nested_span": {"enabled"},
        "selection": {"enabled"},
        "user_visible_labeling": {"page_exclusive"},
    },
    "kindle_title_metadata": {
        "cde_content_type": {
            "EBOK",
            "EBSP",
            "MAGZ",
            "PDOC",
        },
        "ASIN": ANY,
        "asset_id": ANY,
        "author": ANY,
        "author_pronunciation": ANY,
        "book_id": ANY,
        "content_id": ANY,
        "cover_image": ANY,
        "description": ANY,
        "dictionary_lookup": ANY,
        "editionVersion": ANY,
        "imprint_pronunciation": ANY,
        "is_dictionary": {True},
        "is_sample": TF,
        "issue_date": ANY,
        "itemType": {"MAGZ"},
        "language": ANY,
        "override_kindle_font": TF,
        "parent_asin": ANY,
        "periodicals_generation_V2": {"true"},
        "publisher": ANY,
        "title": ANY,
        "title_pronunciation": ANY,
        "updateTime": ANY,
    },
    "metadata": {
        "ASIN": ANY,
        "asset_id": ANY,
        "author": ANY,
        "binding_direction": {"binding_direction_left"},
        "cde_content_type": {
            "EBOK",
            "MAGZ",
            "PDOC",
        },
        "cover_image": ANY,
        "cover_page": ANY,
        "doc_sym_publication_id": ANY,
        "description": ANY,
        "issue_date": ANY,
        "language": ANY,
        "orientation": {"portrait", "landscape"},
        "parent_asin": ANY,
        "publisher": ANY,
        "reading_orders": ANY,
        "support_landscape": TF,
        "support_portrait": TF,
        "target_NarrowDimension": ANY,
        "target_WideDimension": ANY,
        "title": ANY,
        "version": {1.0},
        "volume_label": ANY,
    },
}


KNOWN_AUXILIARY_METADATA = {
    "ANCHOR_REFERRED_BY_CONTAINERS": ANY,
    "auxData_resource_list": ANY,
    "base_line": ANY,
    "button_type": {1},
    "checkbox_state": ANY,
    "dropDown_count": ANY,
    "filename.opf": ANY,
    "has_large_data_table": TF,
    "IsSymNameBased": TF,
    "IS_TARGET_SECTION": {True},
    "kSectionContainsAVI": {True},
    "links_extracted": {True},
    "link_from_text": TF,
    "location": ANY,
    "mime": {"Audio", "Figure", "Video"},
    "ModifiedContentInfo": ANY,
    "modified_time": ANY,
    "most-common-computed-style": ANY,
    "namespace": {"KindleConversion"},
    "num-dual-covers-removed": {1},
    "page_rotation": {0, 1},
    "plugin_group_list": ANY,
    "resizable_plugin": TF,
    "resource_stream": ANY,
    "size": ANY,
    "SourceIdContentInfo": ANY,
    "target": ANY,
    "text_baseline": ANY,
    "text_ext": {1},
    "type": {"resource"},
    "yj.dictionary.first_head_word": ANY,
    "yj.dictionary.inflection_rules": ANY,
}


KNOWN_KCB_DATA = {
    "book_state": {
        "book_input_type": [
            0,
            1,
            2,
            3,
            4,
            6,
            7,
        ],
        "book_reading_direction": [
            0,
            2,
        ],
        "book_target_type": [
            1,
            2,
            3,
        ],
    },
    "content_hash": {},
    "metadata": {
        "book_path": ANY,
        "edited_tool_versions": KNOWN_METADATA["kindle_audit_metadata"][
            "creator_version"
        ],
        "format": ["yj"],
        "global_styling": TF,
        "id": ANY,
        "log_path": ANY,
        "platform": ["mac", "win"],
        "quality_report": ANY,
        "source_path": ANY,
        "tool_name": ["KC", "KPR", "KTC", "Kindle Previewer 3"],
        "tool_version": KNOWN_METADATA["kindle_audit_metadata"]["creator_version"],
    },
    "tool_data": {
        "cache_path": ANY,
        "created_on": ANY,
        "last_modified_time": ANY,
        "link_extract_choice": TF,
        "link_notification_preference": TF,
    },
}


def is_known_generator(kfxgen_application_version, kfxgen_package_version):
    if (
        kfxgen_application_version == ""
        or kfxgen_application_version.startswith("kfxlib")
        or kfxgen_application_version.startswith("KC")
        or kfxgen_application_version.startswith("KPR")
    ):
        return True

    if kfxgen_package_version in PACKAGE_VERSION_PLACEHOLDERS:
        kfxgen_package_version = ""

    return (kfxgen_application_version, kfxgen_package_version) in KNOWN_KFX_GENERATORS


def is_known_feature(cat, key, val):
    vals = KNOWN_FEATURES.get(cat, {}).get(key, [])
    return vals is ANY or val in vals


def is_known_metadata(cat, key, val):
    vals = KNOWN_METADATA.get(cat, {}).get(key, [])
    return vals is ANY or val in vals


def is_known_aux_metadata(key, val):
    vals = KNOWN_AUXILIARY_METADATA.get(key, [])
    return vals is ANY or val in vals


def is_known_kcb_data(cat, key, val):
    vals = KNOWN_KCB_DATA.get(cat, {}).get(key, [])
    return vals is ANY or val in vals
