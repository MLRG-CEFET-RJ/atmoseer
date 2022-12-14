import pandas as pd
import numpy as np
import sys, getopt, os, re


def corrige_txt(nom_estacao, ano, mes):
    for num1 in ano:
        for num2 in mes:
            file = "../RAW_data/COR/meteorologica/" + nom_estacao + "_" + num1 + num2 + "_Met.txt"
            if os.path.exists(file):
                fin = open(file, "rt")
                if not os.path.exists("../RAW_data/COR/meteorologica/aux_"+ nom_estacao):
                    os.mkdir("../RAW_data/COR/meteorologica/aux_"+ nom_estacao)
                fout = open("../RAW_data/COR/meteorologica/aux_" + nom_estacao + "/" + nom_estacao + "_" + num1 + num2 + "_Met2.txt", "wt")
                count = 0
                for line in fin:
                    count += 1
                    if nom_estacao == 'guaratiba':
                        fout.write(re.sub('\s+', ' ', line.replace(':40      ', ':00  HBV')))
                    else:
                        fout.write(re.sub('\s+', ' ', line.replace(':00      ', ':00  HBV')))
                    fout.write('\n')
                if count == 6:
                    fout.write('01/' + num2 + '/'+num1 + ' 00:00:00 HBV ND ND ND ND ND ND')
                fin.close()
                fout.close()
            else:
                pass


def gera_dataset(nom_estacao, ano, mes):
    data1 = pd.DataFrame()

    for num1 in ano:
        check = 0
        for num2 in mes:
            texto = '../RAW_data/COR/meteorologica/aux_' + nom_estacao + '/' + nom_estacao + '_' + num1 + num2 + '_Met2.txt'
            if os.path.exists(texto):
                data1 = pd.read_csv(texto, sep=' ', skiprows=[0, 1, 2, 3, 4, 5], header=None)
                if len(data1.columns) == 10:
                    data1.columns = ['Dia', 'Hora', 'HBV', 'Chuva', 'DirVento','VelVento', 'Temperatura', 'Pressao', 'Umidade', 'teste']
                    del data1["teste"]
                else:
                    data1.columns = ['Dia', 'Hora', 'HBV', 'Chuva', 'DirVento','VelVento', 'Temperatura', 'Pressao', 'Umidade']
                data1['Chuva'] = data1['Chuva'][~data1['Chuva'].isin(['-', 'ND'])].astype(float)
                data1['Umidade'] = data1['Umidade'][data1['Umidade'] != 'ND'].astype(float)
                data1['Temperatura'] = data1['Temperatura'][data1['Temperatura'] != 'ND'].astype(float)
                data1['DirVento'] = data1['DirVento'][~data1['DirVento'].isin(['-', 'ND'])].astype(float)
                data1['VelVento'] = data1['VelVento'][data1['VelVento'] != 'ND'].astype(float)
                data1['Pressao'] = data1['Pressao'][data1['Pressao'] != 'ND'].astype(float)
                data1['Dia'] = pd.to_datetime(data1['Dia'], format='%d/%m/%Y')
                ano_aux = num1
                mes_aux = num2
                print(num1 + '/' + num2)
                check = 1
                break
            else:
                pass
        if check == 1:
            break
        
    ano1 = list(map(str,range(int(ano_aux),2022)))
    mes1 = list(range(int(mes_aux),13))
    mes1 = [str(i).rjust(2, '0') for i in mes1]

    for num1 in ano1:
        for num2 in mes1:
            texto = '../RAW_data/COR/meteorologica/aux_' + nom_estacao + '/' + nom_estacao + '_' + num1 + num2 + '_Met2.txt'
            if os.path.exists(texto):
                data2 = pd.read_csv(texto, sep=' ', skiprows=[0, 1, 2, 3, 4, 5], header=None, on_bad_lines='skip')
                if len(data2.columns) == 10:
                    data2.columns = ['Dia', 'Hora', 'HBV', 'Chuva', 'DirVento','VelVento', 'Temperatura', 'Pressao', 'Umidade', 'teste']
                    del data2["teste"]
                else:
                    data2.columns = ['Dia', 'Hora', 'HBV', 'Chuva', 'DirVento','VelVento', 'Temperatura', 'Pressao', 'Umidade']
                data2['Chuva'] = data2['Chuva'][~data2['Chuva'].isin(['-', 'ND'])].astype(float)
                data2['Umidade'] = data2['Umidade'][data2['Umidade'] != 'ND'].astype(float)
                data2['Temperatura'] = data2['Temperatura'][~data2['Temperatura'].isin(['-', 'ND'])].astype(float)
                data2['DirVento'] = data2['DirVento'][~data2['DirVento'].isin(['-', 'ND'])].astype(float)
                data2['VelVento'] = data2['VelVento'][data2['VelVento'] != 'ND'].astype(float)
                data2['Pressao'] = data2['Pressao'][data2['Pressao'] != 'ND'].astype(float)
                data2['Dia'] = pd.to_datetime(data2['Dia'], format='%d/%m/%Y')
                saida = pd.concat([data1, data2])
                data1 = saida
                del saida
            else:
                pass
    if num1 == ano_aux:
        mes1 = list(range(1,13))
        mes1 = [str(i).rjust(2, '0') for i in mes1]
    data1 = data1.replace('ND', np.NaN)
    data1 = data1.replace('-', np.NaN)
    data1['estacao'] = nom_estacao
    data1.to_csv(nom_estacao + '.csv')
    data_aux = data1
    del data1, data2
    return data_aux


def processamento(nom_estacao, all = 0):
    ano  = list(map(str,range(1997,2022)))
    mes = list(range(1,13))
    mes = [str(i).rjust(2, '0') for i in mes]

    if all < 1:
        corrige_txt(nom_estacao, ano, mes)
        
        data = gera_dataset(nom_estacao, ano, mes)
        del data
    else:
        cor_est = ['alto_da_boa_vista','guaratiba','iraja','jardim_botanico','riocentro','santa_cruz','sao_cristovao','vidigal']
        for i in cor_est:
            corrige_txt(nom_estacao, ano, mes)
            
            data = gera_dataset(nom_estacao, ano, mes)
            del data

def myfunc(argv):
    arg_file = ""
    arg_all = 0
    arg_help = "{0} -s <station> -a <all>".format(argv[0])
    
    try:
        opts, args = getopt.getopt(argv[1:], "hs:a:", ["help", "sta=", "all="])
    except:
        print(arg_help)
        sys.exit(2)
    
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(arg_help)  # print the help message
            sys.exit(2)
        elif opt in ("-s", "--sta"):
            arg_file = arg
        elif opt in ("-a", "--all"):
            arg_all = 1

    if arg_file == '':
        print('Digite alguma das esta????es : alto_da_boa_vista, guaratiba, iraja, jardim_botanico, riocentro, santa_cruz, sao_cristovao, vidigal')
    else:
        processamento(arg_file,arg_all)


if __name__ == "__main__":
    myfunc(sys.argv)


