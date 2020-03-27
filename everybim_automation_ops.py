#!/usr/bin/env python
# coding=utf-8

import sys
import json
import os
import shutil
import time
from optparse import OptionParser

import regex as re
import requests
import platform

global_result = 0
global_action_id = ''
global_branch = ''


class oem_config:
    def __init__(self, config):
        if 'appName' in config and len(config['appName']) > 0:
            self.name = config['appName']
        else:
            self.name = 'EveryBIM'

        # if 'versionName' in config and len(config['versionName']) > 0:
        #     self.version_name = config['versionName']
        # else:
        #     self.version_name = ''

        if 'serverAddress' in config and len(config['serverAddress']) > 0:
            self.server_address = config['serverAddress']
        else:
            self.server_address = "https://cloud.everybim.net"

        if 'packageId' in config and len(config['packageId']) > 0:
            self.package_id = config['packageId']
        else:
            self.package_id = ''

        if 'logoAddress' in config and len(config['logoAddress']) > 0:
            self.app_logo_address = config['logoAddress']
        else:
            self.app_logo_address = ''

        if 'splashAddress' in config and len(config['splashAddress']) > 0:
            self.splash_logo_address = config['splashAddress']
        else:
            self.splash_logo_address = ''


def main(option):
    global global_result
    config = oem_config(json.loads(option.config))
    try:
        update_ops_status('开始打包')
        clear_env()
        resolve_svg(config.app_logo_address, config.splash_logo_address)
        has_base = check_base_apk(option.version)
        if has_base:
            compile_base(config.name, option.version, config.server_address, config.package_id)
        else:
            compile_source(config.name, option.version, config.server_address, config.package_id)

    except Exception as e:
        global_result = 1
        update_ops_status("编译失败: " + str(e))
        flush_out(e)
    finally:
        # 放弃所有本地修改
        os.system("git checkout .")

    if global_result > 0:
        flush_out("打包失败")
        exit(1)
    else:
        update_ops_status("编译成功")
        flush_out("打包成功")
        exit(0)


def compile_base(name, version_name, server_address, package_id):
    prepare_base_env()
    unpack_base_apk()
    replace_base_configs(name, version_name, server_address)
    replace_base_pics()
    compile_base_code()
    upload_to_server('./build_base/sign.apk', package_id)


def compile_base_code():
    flush_out('开始增量编译打包 约1-3分钟')
    update_ops_status('增量编译(1-3分钟)')
    flush_out('开始重新编译')
    execute('apktool b ./build_base/base -o ./build_base/unsign.apk')
    flush_out('重新编译完成')
    flush_out('开始重新签名')
    execute('apksigner sign --ks /jks/ezbim.jks ' +
            '--ks-key-alias ezbim ' +
            '--ks-pass pass:ezbim123 ' +
            '--key-pass pass:ezbim123 ' +
            '--v2-signing-enabled false ' +
            '--out ./build_base/sign.apk ./build_base/unsign.apk')
    flush_out('重新签名完成')
    flush_out('增量编译打包完成')
    update_ops_status('编译完成等待上传')


def replace_base_configs(name, version_name, server_address):
    global global_result
    flush_out('开始替换增量编译APP配置项')
    application_name_pattern = "(?<=.*android:label=\")\\S*(?=\")"
    server_address_pattern = "(?<=.*android:name=\"SERVER_ADDRESS\" android:value=\").*(?=\")"
    version_name_pattern = "(?<=\\s*versionName:\\s)[\\d\\.]*(?=\\s*)"

    root_dir = os.getcwd()
    manifest_path = os.path.join(root_dir, 'build_base', 'base', 'AndroidManifest.xml')
    if not os.path.exists(manifest_path):
        raise RuntimeError('解压Manifest文件丢失')

    manifest_file = open(manifest_path, "r+")
    manifest_txt = manifest_file.read()
    if len(name) > 0:
        application_name_pattern = re.compile(application_name_pattern)
        if len(application_name_pattern.findall(manifest_txt)) == 0:
            flush_out('跳过APP名称替换')
        else:
            manifest_txt = application_name_pattern.sub(name, manifest_txt)
            flush_out('完成APP名称替换')
    else:
        flush_out('跳过APP名称替换')

    if len(server_address_pattern) > 0:
        server_address_pattern = re.compile(server_address_pattern)
        if len(server_address_pattern.findall(manifest_txt)) == 0:
            flush_out('跳过APP服务器地址替换')
        else:
            manifest_txt = server_address_pattern.sub(server_address, manifest_txt)
            flush_out('完成APP服务器地址替换')
    else:
        flush_out('跳过APP服务器地址替换')

    manifest_file.seek(0)  # 移动文件指针
    manifest_file.truncate()  # 同时清除文件内容
    manifest_file.write(manifest_txt)  # 将新的配置文件写入
    manifest_file.close()

    apktool_path = os.path.join(root_dir, 'build_base', 'base', 'apktool.yml')
    if not os.path.exists(apktool_path):
        raise RuntimeError('解压Apktool文件丢失')

    apktool_file = open(apktool_path, "r+")
    apktool_txt = apktool_file.read()
    if len(version_name) > 0:
        version_name_pattern = re.compile(version_name_pattern)
        if len(version_name_pattern.findall(apktool_txt)) == 0:
            flush_out('跳过APP版本名称替换')
        else:
            apktool_txt = version_name_pattern.sub(version_name, apktool_txt)
            flush_out('完成APP版本名称替换')
    else:
        flush_out('跳过APP版本名称替换')

    apktool_file.seek(0)  # 移动文件指针
    apktool_file.truncate()  # 同时清除文件内容
    apktool_file.write(apktool_txt)  # 将新的配置文件写入
    apktool_file.close()
    flush_out('替换增量编译APP配置项完成')


def replace_base_pics():
    flush_out('开始替换增量编译LOGO文件')
    root_dir = os.getcwd()
    logo_path = os.path.join(root_dir, "logo")
    resource_path = os.path.join(
        root_dir,
        'build_base',
        'base',
        'res'
    )
    if os.path.isdir(logo_path):
        flush_out('开始替换图标LOGO文件')
        replace_res_files(logo_path, resource_path)
        flush_out('替换图标LOGO文件完成')
    else:
        flush_out('开始替换原始图标LOGO文件')
        replace_original_logo_res(resource_path)
        flush_out('替换原始图标LOGO文件完成')

    splash_path = os.path.join(root_dir, "splash")
    if os.path.isdir(splash_path):
        flush_out('开始替换启动页LOGO文件')
        replace_res_files(splash_path, resource_path)
        flush_out('替换启动页LOGO文件完成')
    else:
        flush_out('开始替换原始启动页LOGO文件')
        replace_original_splash_res(resource_path)
        flush_out('替换原始启动页LOGO文件完成')

    flush_out('增量编译LOGO文件替换完成')


def replace_original_logo_res(resource_path):
    root_dir = os.getcwd()
    logo_paths = [
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'mipmap-hdpi',
                     'ic_launcher_logo.png'),
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'mipmap-mdpi',
                     'ic_launcher_logo.png'),
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'mipmap-xhdpi',
                     'ic_launcher_logo.png'),
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'mipmap-xxhdpi',
                     'ic_launcher_logo.png'),
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'mipmap-xxxhdpi',
                     'ic_launcher_logo.png')
    ]
    logo_path = os.path.join(root_dir, "logo")
    for path in logo_paths:
        copy_file(path, logo_path + os.sep +
                  os.path.basename(os.path.dirname(path)) +
                  os.sep + os.path.basename(path))
    replace_res_files(logo_path, resource_path)


def replace_original_splash_res(resource_path):
    root_dir = os.getcwd()
    splash_paths = [
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'drawable-hdpi',
                     'main_splash_logo.png'),
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'drawable-mdpi',
                     'main_splash_logo.png'),
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'drawable-xhdpi',
                     'main_splash_logo.png'),
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'drawable-xxhdpi',
                     'main_splash_logo.png'),
        os.path.join(root_dir, 'app', 'src', 'main', 'res', 'drawable-xxxhdpi',
                     'main_splash_logo.png')
    ]
    splash_path = os.path.join(root_dir, "splash")
    for path in splash_paths:
        copy_file(path, splash_path + os.sep +
                  os.path.basename(os.path.dirname(path)) +
                  os.sep + os.path.basename(path))
    replace_res_files(splash_path, resource_path)


def unpack_base_apk():
    flush_out('开始解压基准包')
    update_ops_status('开始解包')
    execute('apktool d -f ./build_base/base.apk -o ./build_base/base')
    flush_out('解压基准包完成')
    update_ops_status('解包完成')


def prepare_base_env():
    flush_out('准备增量编译环境')
    if not os.path.exists('./build_base'):
        os.makedirs('./build_base')
    base_path = base_apk_path()
    copy_file(base_path, os.path.join('./build_base', 'base.apk'))
    execute('cd ./build_base')
    flush_out('增量编译环境准备完成')


def compile_source(name, version_name, server_address, package_id):
    prepare_source_env()
    replace_source_configs(name, version_name, server_address)
    replace_source_pics()
    compile_source_code(name)
    upload_to_server('./apk', package_id)
    copy_base_apk('./apk')


def clear_env():
    # 清理环境
    # 移除所有build文件夹
    flush_out('清理编译环境')
    execute('rm -rf *.hprof')
    execute('rm -rf *.svg')
    execute('rm -rf logo')
    execute('rm -rf splash')
    execute('rm -rf apk')
    execute('rm -rf build_log.txt')


def copy_base_apk(path):
    global global_branch
    if os.path.isdir(path):
        for item in os.listdir(path):
            if not item.__contains__('C8BIM'):
                _path = redirect_path(path, item)
                version_name = global_branch
                if is_linux():
                    version_code = execute_result(
                        "aapt dump badging " + _path +
                        "|grep -o -P versionCode='\\S*' |grep -o -P '\\d+'")
                else:
                    version_code = execute_result(
                        "aapt dump badging " + _path +
                        "|grep -o versionCode='\\S*' |grep -o -E '\\d+'")
                if len(version_name) > 0 and len(version_code) > 0:
                    source = os.path.join(path, item)
                    copy_name = version_name + '_' + version_code
                    copy_file(source, os.path.join('../build_releases', copy_name))


def upload_to_server(file_path, package_id):
    if len(package_id) > 5:
        flush_out('准备上传包管理平台 约1-3分钟')
        update_ops_status('安装包上传(1-3分钟)')
        if os.path.isdir(file_path):
            for item in os.listdir(file_path):
                upload_apk(os.path.join(file_path, item), package_id)
        else:
            upload_apk(file_path, package_id)
    else:
        flush_out('跳过上传包管理平台')


def upload_apk(file_path, package_id):
    upload_address = "https://console.ezbim.net/api/files"
    application_address = "https://console.ezbim.net/api/applications"
    file = {'file': open(file_path, 'rb')}
    result = requests.post(upload_address, files=file)
    json_result = json.loads(result.text)
    if "file" in json_result.keys():
        data = {'fileId': json_result['file'],
                'device': 'android',
                'forced': 'false',
                "installPackageId": package_id}
        result = requests.post(application_address, data=data)
        json_result = json.loads(result.text)
        if "_id" in json_result.keys():
            flush_out(
                "上传成功 : https://console.ezbim.net/packages?id=" + json_result['_id'])
        else:
            flush_out("上传包管理平台失败")


def compile_source_code(name):
    flush_out('开始全量编译打包 约15-25分钟')
    update_ops_status('全量编译(15-25分钟)')
    cscec_chanel = 'C8BIM'
    if cscec_chanel == name:
        chanel = 'cscec'
    else:
        chanel = 'everybim'
    execute('gradle' + ' assemble' + chanel.capitalize())
    flush_out('全量编译打包完成')
    update_ops_status('编译完成等待上传')


def prepare_source_env():
    flush_out('准备全量编译环境')
    execute('gradle clean')
    if not os.path.exists('../build_releases'):
        os.makedirs('../build_releases')
    flush_out('全量编译环境准备完成')


def replace_source_pics():
    flush_out('开始替换全量编译LOGO文件')
    root_dir = os.getcwd()
    logo_path = os.path.join(root_dir, "logo")
    resource_path = os.path.join(
        root_dir,
        'app',
        'src',
        'main',
        'res'
    )
    if os.path.isdir(logo_path):
        flush_out('开始替换图标LOGO文件')
        replace_res_files(logo_path, resource_path)
        flush_out('替换图标LOGO文件完成')
    else:
        flush_out('开始替换原始图标LOGO文件')
        replace_original_logo_res(resource_path)
        flush_out('替换原始图标LOGO文件完成')

    splash_path = os.path.join(root_dir, "splash")
    if os.path.isdir(splash_path):
        flush_out('开始替换启动页LOGO文件')
        replace_res_files(splash_path, resource_path)
        flush_out('替换启动页LOGO文件完成')
    else:
        flush_out('开始替换原始启动页LOGO文件')
        replace_original_splash_res(resource_path)
        flush_out('替换原始启动页LOGO文件完成')

    flush_out('全量编译LOGO文件替换完成')


def replace_res_files(source, resource_path):
    for child in os.listdir(source):
        if os.path.isdir(os.path.join(source, child)):
            for item in os.listdir(os.path.join(source, child)):
                make_dir(os.path.join(resource_path, child))
                flush_out('替换 ' + child + " " + item + ' 文件')
                copy_file(os.path.join(source, child, item),
                          os.path.join(resource_path, child, item))


def copy_file(source, target):
    make_dir(os.path.dirname(target))
    shutil.copyfile(source, target)


def replace_source_configs(name, version_name, server_address):
    global global_result
    flush_out('开始替换全量编译APP配置项')
    version_name_pattern = "(?<=versionName\\s+:\\s+\").*?(?=\")"
    application_name_pattern = "(?<=applicationName\\s*:\\s*\").*?(?=\")"
    server_address_pattern = "(?<=serverAddress\\s*:\\s*\").*?(?=\")"
    root_dir = os.getcwd()
    config_path = os.path.join(root_dir, "app.gradle")
    if not os.path.exists(config_path):
        global_result = 1
        raise RuntimeError('APP配置文件丢失，请添加配置文件')
    config_file = open(config_path, "r+")
    config_txt = config_file.read()
    if len(version_name) > 0:
        version_name_pattern = re.compile(version_name_pattern)
        if len(version_name_pattern.findall(config_txt)) == 0:
            flush_out('跳过APP版本名称替换')
        else:
            config_txt = version_name_pattern.sub(version_name, config_txt)
            flush_out('完成APP版本名称替换')
    else:
        flush_out('跳过APP版本名称替换')
    if len(name) > 0:
        application_name_pattern = re.compile(application_name_pattern)
        if len(application_name_pattern.findall(config_txt)) == 0:
            flush_out('跳过APP名称替换')
        else:
            config_txt = application_name_pattern.sub(name, config_txt)
            flush_out('完成APP名称替换')
    else:
        flush_out('跳过APP名称替换')
    if len(server_address_pattern) > 0:
        server_address_pattern = re.compile(server_address_pattern)
        if len(server_address_pattern.findall(config_txt)) == 0:
            flush_out('跳过APP服务器地址替换')
        else:
            config_txt = server_address_pattern.sub(server_address, config_txt)
            flush_out('完成APP服务器地址替换')
    else:
        flush_out('跳过APP服务器地址替换')

    config_file.seek(0)  # 移动文件指针
    config_file.truncate()  # 同时清除文件内容
    config_file.write(config_txt)  # 将新的配置文件写入
    config_file.close()
    flush_out('替换全量编译APP配置项完毕')


def resolve_svg(app_logo_address, splash_logo_address):
    flush_out('开始下载图标文件')
    if len(app_logo_address) > 0:
        flush_out('开始下载APP图标')
        execute('wget ' + app_logo_address + ' -O logo.svg')
        configs = [
            svg_config('logo' + os.sep + 'mipmap-mdpi', 'ic_launcher_logo', '1.0'),
            svg_config('logo' + os.sep + 'mipmap-hdpi', 'ic_launcher_logo', '1.5'),
            svg_config('logo' + os.sep + 'mipmap-xhdpi', 'ic_launcher_logo', '2.0'),
            svg_config('logo' + os.sep + 'mipmap-xxhdpi', 'ic_launcher_logo', '3.0'),
            svg_config('logo' + os.sep + 'mipmap-xxxhdpi', 'ic_launcher_logo', '4.0')]
        for item in configs:
            svg_resize('logo.svg', item)
        flush_out('APP图标裁剪完成')
    else:
        flush_out('跳过下载APP图标')

    if len(splash_logo_address) > 0:
        flush_out('开始下载启动页图标')
        execute('wget ' + splash_logo_address + ' -O splash.svg')
        configs = [
            svg_config('splash' + os.sep + 'drawable-mdpi', 'main_splash_logo', '1.0'),
            svg_config('splash' + os.sep + 'drawable-hdpi', 'main_splash_logo', '1.5'),
            svg_config('splash' + os.sep + 'drawable-xhdpi', 'main_splash_logo', '2.0'),
            svg_config('splash' + os.sep + 'drawable-xxhdpi', 'main_splash_logo', '3.0'),
            svg_config('splash' + os.sep + 'drawable-xxxhdpi', 'main_splash_logo', '4.0')]
        for item in configs:
            svg_resize('splash.svg', item)
        flush_out('启动页图标裁剪完成')
    else:
        flush_out('跳过下载启动页图标')
    flush_out('下载图标文件完毕')


def svg_resize(svg_path, size_config):
    make_dir(size_config['dir'])
    execute("rsvg-convert -f png -d 320 -p 320" +
            " -z " + size_config['zoom'] +
            " -o " + size_config['dir'] +
            os.sep + size_config['name'] + '.png' + " " + svg_path)


def svg_config(dir_name, name, zoom):
    return {'zoom': zoom, 'dir': dir_name, 'name': name}


def check_base_apk(version_name):
    if version_name == 'C8BIM':
        return False
    base_path = base_apk_path()
    if len(base_path) == 0:
        return False
    return os.path.exists(base_path)


def base_apk_path():
    global global_branch
    version_name = global_branch
    if is_linux():
        version_code = execute_result("cat app.gradle| grep versionCode| grep -o -P '\\d+'")
    else:
        version_code = execute_result("cat app.gradle| grep versionCode| grep -o -E '\\d+'")
    if len(version_name) == 0 or len(version_code) == 0:
        return ''
    base_name = version_name + '_' + version_code
    base_path = os.path.join('../build_releases', base_name)
    return base_path


def make_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def execute(command):
    global global_result
    result = os.system(command + ' > build_log.txt 2>&1')
    if result > 0:
        global_result = result
        raise Exception("执行失败: " + command)


def execute_result(command):
    execute(command)
    result = os.popen(command)
    return str(result.read()).strip()


def update_ops_status(status):
    global global_action_id
    if global_action_id == "":
        return
    update_url = "https://console.ezbim.net/api/automation/android/actions/" + global_action_id
    params = {"status": status}
    requests.put(update_url, json=params)


def flush_out(args):
    print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + " ===> " + str(args))
    sys.stdout.flush()


def parser_config():
    parser = OptionParser()
    parser.add_option("-c", "--config",
                      type="string",
                      metavar="config")
    parser.add_option("-a", "--action",
                      type="string",
                      metavar="action",
                      default="")
    parser.add_option("-v", "--version",
                      type="string",
                      metavar="version")
    parser.add_option("-b", "--branch",
                      type="string",
                      metavar="branch")
    (option, _) = parser.parse_args()
    return option


def redirect_path(path, *paths):
    _path = os.path.join(path, *paths)
    _path = _path.replace('(', '\\(').replace(')', '\\)')
    return _path


def is_linux():
    return platform.system() == 'Linux'


if __name__ == '__main__':
    option = parser_config()
    reload(sys)
    sys.setdefaultencoding('utf8')
    flush_out(option)
    global_action_id = option.action
    global_branch = option.branch
    main(option)
